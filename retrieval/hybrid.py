"""Hybrid retrieval: page BM25 + chunk BM25 + chunk dense, fused with RRF (Step 5).

**MEASURED OUTCOME: this does not beat the page baseline, and the UI does not use it.**
On the 26 answerable eval questions the page-level BM25 baseline (`ui/retrieval.py`)
scores recall@5 25/26 with MRR 0.885. Twenty-four weight combinations of this fusion
were measured (`eval/run_hybrid.py`, weights page 3-5 / chunk 0.5-1 / dense 0-1); the
best reached recall@5 24/26 with MRR 0.486 and most reached 18-20/26. The page list
alone through this same code path reproduces 25/26 and 0.885 exactly, so the fusion is
what loses, not the plumbing. It stays in the repository as the measured evidence, not
as the retriever in use - see `reports/retrieval-step5.md` and PROPOSED D-057.

TODO(step-05): the next attempt worth trying is a cross-encoder reranker over the
baseline's top 30 pages (same candidate set, so recall cannot drop), or normalising
scores per list instead of discarding magnitude with RRF. Do not re-tune RRF weights
on these 26 questions: that is fitting the test set.

Three signals, and each is there for a measured reason rather than symmetry:

- **page BM25** (`ui/retrieval.py`) is the baseline the eval set was measured on: 25 of
  26 answerable questions at rank 1, MRR 0.885. A whole page keeps terms together that
  chunking splits apart — q010's "correlation coefficient for equation (2)" is on one
  page but in no single chunk — so dropping this signal was measurable damage, not a
  simplification: two-signal chunk fusion scored 24/26 at rank 1, MRR 0.833.
- **chunk BM25** points at the paragraph, which is what the answer is built from.
- **chunk dense** (bge-small) reaches paraphrases BM25 cannot: `rainfall` against
  `precipitation`. It is the only signal that answers a question phrased differently
  from the source.

**RRF, not score addition.** BM25 scores and cosine distances share no scale, so they
are fused by rank: `weight / (60 + rank)` per list. Fusing per *page* (the best chunk on
a page defines that page) rather than summing all of a page's chunks, because summing
let a long document with many mediocre matches outrank the page holding the answer
(measured: recall@5 18/26, MRR 0.459).

A citation is a page: `file` + `page_start` of the best matching chunk, or the page
itself when only the page-level list found it. Hits keep the keys
`ui/retrieval.search()` returns, so the UI does not care which retriever answered.

Usage:
    from retrieval import hybrid
    index = hybrid.build()
    hits = hybrid.search(index, "What was the 24-hour rainfall at Tistung?", k=4)
    print(hits[0]["label"], hits[0]["page"], hits[0]["snippet"][:80])
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# `ui.retrieval` owns the page index, the tokenizer, the snippet cutter and the BM25
# scorer. Importing them keeps one definition of "a token" and one scorer across both
# granularities, so the comparison against the baseline cannot drift.
from ui import retrieval as pages_retrieval      # noqa: E402
from ui.retrieval import BM25, context_for, label_for, snippet, tokens  # noqa: E402

CHUNKS = ROOT / "index" / "chunks.jsonl"
DB = ROOT / "index" / "lancedb"
TABLE = "chunks"
MODEL_FOLDER = "bge-small-en-v1.5"
MODELS = ROOT / "models"
CANDIDATES = 40          # results each list contributes to the fusion
RRF_K = 60               # the standard RRF constant

# Weights: the two lexical lists carry the exact strings this eval set asks for, and
# the dense list adds paraphrases without being allowed to outvote them. These are
# recorded in DECISIONS.md (PROPOSED) with the numbers that chose them.
WEIGHTS = {"page": 1.0, "chunk": 1.0, "dense": 0.7}


def _read_chunks(path: pathlib.Path = CHUNKS) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"missing {path}: run `python -m chunk.cli build` first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


class Dense:
    """bge-small queries against the LanceDB table `chunk.dense` wrote."""

    def __init__(self, db: pathlib.Path = DB, table: str = TABLE):
        import lancedb
        from sentence_transformers import SentenceTransformer

        model_path = MODELS / MODEL_FOLDER
        if not model_path.exists():
            raise SystemExit(f"missing model folder: {model_path}")
        self.table = lancedb.connect(str(db)).open_table(table)
        self.model = SentenceTransformer(str(model_path), device="cpu")

    def search(self, query: str, limit: int = CANDIDATES) -> list[str]:
        """chunk ids, best first (cosine distance: lower is nearer)."""
        vector = self.model.encode([query], convert_to_numpy=True,
                                   normalize_embeddings=True)[0]
        rows = self.table.search(vector).limit(limit).to_list()
        return [row["chunk_id"] for row in rows]


def build(use_dense: bool = True) -> dict:
    """Load chunks and pages, index both for BM25, and open the dense table."""
    chunks = _read_chunks()
    page_index = pages_retrieval.build()
    dense = None
    dense_error = ""
    if use_dense and DB.exists():
        try:
            dense = Dense()
        except Exception as exc:  # noqa: BLE001 - a broken index must not kill BM25
            dense_error = f"{exc.__class__.__name__}: {exc}"
    elif use_dense:
        dense_error = f"{DB} missing (run `python -m chunk.dense`)"
    if dense_error:
        print(f"[hybrid] dense side off: {dense_error}", file=sys.stderr)

    by_id = {chunk["chunk_id"]: position for position, chunk in enumerate(chunks)}
    return {
        "chunks": chunks,
        "by_id": by_id,
        # Every chunk, not only the ones BM25 scored: the dense list names chunk ids
        # that never matched a query term, and both lists must map to a page.
        "meta": {chunk["chunk_id"]: ((chunk["file"], int(chunk["page_start"])), chunk)
                 for chunk in chunks},
        "bm25": BM25(chunks),
        "pages": page_index,
        "page_bm25": BM25(page_index["pages"]),
        "dense": dense,
        "dense_error": dense_error,
    }


def _chunk_list(index: dict, query: str) -> list[str]:
    """Chunk ids ranked by BM25, best first, at most CANDIDATES of them."""
    chunks: list[dict] = index["chunks"]
    terms = tokens(query)
    reader: BM25 = index["bm25"]
    scored = []
    for position, chunk in enumerate(chunks):
        score = reader.score(terms, position)
        if score > 0:
            scored.append((score, chunk["chunk_id"]))
    scored.sort(reverse=True)
    return [chunk_id for _, chunk_id in scored[:CANDIDATES]]


def search(index: dict, query: str, k: int = 4) -> list[dict]:
    """Top-k pages for a question, best first, fused from three ranked lists."""
    terms = tokens(query)
    if not terms:
        return []

    lexical = _chunk_list(index, query)
    dense = index["dense"].search(query, CANDIDATES) if index["dense"] else []
    cue: dict = index["meta"]

    reader: BM25 = index["page_bm25"]
    page_scores = []
    for position, page in enumerate(index["pages"]["pages"]):
        if not page["text"]:
            continue
        score = reader.score(terms, position)
        if score > 0:
            page_scores.append((score, position))
    page_scores.sort(reverse=True)
    page_ranked = [(index["pages"]["pages"][position]["doc"],
                    index["pages"]["pages"][position]["page"])
                   for _, position in page_scores[:CANDIDATES]]

    # {page key: [fused score, best chunk id or None, list the best chunk came from]}
    fused: dict[tuple[str, int], list] = {}
    for name, ranked in (("chunk", lexical), ("dense", dense)):
        for rank, chunk_id in enumerate(ranked, start=1):
            key, _chunk = cue[chunk_id]
            entry = fused.setdefault(key, [0.0, None, 2.0])
            contribution = WEIGHTS[name] / (RRF_K + rank)
            entry[0] += contribution
            if contribution > entry[2]:
                entry[2], entry[1] = contribution, chunk_id
    for rank, key in enumerate(page_ranked, start=1):
        entry = fused.setdefault(key, [0.0, None, 2.0])
        entry[0] += WEIGHTS["page"] / (RRF_K + rank)

    order = sorted(fused.items(), key=lambda item: -item[1][0])
    text_by_page = {(p["doc"], p["page"]): p["text"] for p in index["pages"]["pages"]}
    hits = []
    for (doc, page), (score, chunk_id, _source) in order:
        if chunk_id is not None:
            text = cue[chunk_id][1]["text"]
            chunk_type = cue[chunk_id][1].get("type", "text")
        else:
            text = text_by_page.get((doc, page), "")
            chunk_type = "page"
        hits.append({
            "doc": doc,
            "page": page,
            "label": label_for(doc),
            "ocr": False,                  # Step 3 flags OCR pages in the parse
            "score": round(score, 6),
            "chunk_id": chunk_id,
            "type": chunk_type,
            "context": text if chunk_id is not None else context_for(text, terms),
            "snippet": snippet(text, terms),
        })
        if len(hits) >= k:
            break
    return hits


if __name__ == "__main__":
    # Quick manual probe: `python -m retrieval.hybrid "your question"`.
    question = " ".join(sys.argv[1:]) or "What was the 24-hour rainfall at Tistung?"
    loaded = build()
    for hit in search(loaded, question, k=4):
        print(f"{hit['score']:.4f}  {hit['label']} p{hit['page']} [{hit['type']}]  "
              f"{hit['snippet'][:80]}")
