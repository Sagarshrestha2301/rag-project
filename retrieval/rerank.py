"""Cross-encoder reranking of the retrieved pages, behind a flag.

Page BM25 ranks a page by how well the question's words match it, not by whether the page
answers the question. Adding documents moves those rankings even when nothing about the
old pages changed: wave 01 (D-078) turned 8 canary questions from pass to fail while the
gold page was still rank 1, because a 5th passage changed or because BM25's corpus
statistics shifted (D-079).

This module re-scores the top `DEPTH` pages of that list with an English cross-encoder,
which reads the question and a passage together, and keeps the best `k`. Only the order
and the membership of the list change: each passage keeps its own fields, its BM25 score
stays in `score` (the gate's floor and the debug payload read it), and the cross-encoder's
own number is added as `rerank` with the page's original position as `bm25_rank`.

It is behind `CHAT_RERANK=1` until a measured run says keep it, like the two table
experiments (D-069, D-073). With the flag off, `apply()` returns its input untouched, so
the accepted pipeline is exactly what runs.

Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`, downloaded once into
`models/ms-marco-MiniLM-L-6-v2` (see `STATUS.md` for its hashes) and loaded from disk, on
CPU, so the local model keeps the VRAM (rule 10). Measured: 9.9 s to load once and
**409 ms p50 (475 ms max)** for 10 passages, against a ~12 s answer.

Measured 2026-11-22 and **not kept** (D-081): it restores the wave-01 canary total to
37/55 but fails the regression gate in both configurations, so `CHAT_RERANK` ships off.

Usage:
    from corpus import build, search
    from retrieval import rerank

    index = build()

    question = "In Table 2, how many Midhills households do not believe in taboos?"
    hits = search(index, question, k=rerank.depth() if rerank.enabled() else 4)
    if rerank.enabled():
        hits = rerank.apply(hits, question, k=4)
    >>> [(hit["page"], hit["bm25_rank"], round(hit["rerank"], 2)) for hit in hits]
    [(6, 0, 8.31), (12, 2, 4.02), (31, 5, 1.77), (9, 3, -1.20)]
"""

from __future__ import annotations

import os

from corpus import ROOT

FLAG = "CHAT_RERANK"
MODEL = "ms-marco-MiniLM-L-6-v2"
DEPTH = 10            # pages read by the cross-encoder before the list is cut to k
ANCHOR = 0            # BM25 pages kept in front, untouched, before the reranker decides
MAX_CHARS = 1600      # of one passage's context: the cross-encoder reads the first part

_MODEL_CACHE: dict = {"scorer": None}


def enabled() -> bool:
    """Is the reranker switched on for this process?

    Read from the environment on every call rather than captured at import, so a test or
    a measurement can flip it without a fresh interpreter.
    """
    return os.environ.get(FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def depth() -> int:
    """How many pages to retrieve before reranking (never fewer than the caller's k)."""
    try:
        return max(2, int(os.environ.get("CHAT_RERANK_DEPTH", DEPTH)))
    except ValueError:
        return DEPTH


def anchor() -> int:
    """How many of BM25's own top pages stay in front, untouched.

    Measured to matter: reranking all six passages moved the same gold *document* onto
    pages that no longer answered the question (q025-q027, q047), because BM25's own top
    page is often the right one. Zero means the reranker orders the whole list.
    """
    try:
        return max(0, int(os.environ.get("CHAT_RERANK_ANCHOR", ANCHOR)))
    except ValueError:
        return ANCHOR


def cache_suffix() -> str:
    """What to add to the answer cache key, so a reranked answer is not replayed.

    The cache key holds the prompt version; the reranker changes which passages the prompt
    is built from, so an answer produced with it on must not be served with it off (or at
    a different depth). Empty when the flag is off, which keeps today's keys unchanged.
    """
    if not enabled():
        return ""
    kept = anchor()
    return f"+rerank{min(depth(), 9999)}" + (f"a{kept}" if kept else "")


def _default_scorer() -> object:
    """The cross-encoder, loaded once per process from `models/` on CPU."""
    if _MODEL_CACHE["scorer"] is None:
        from sentence_transformers import CrossEncoder

        path = ROOT / "models" / MODEL
        if not path.exists():
            raise RuntimeError(
                f"missing reranker model folder: {path} - download {MODEL} into models/ "
                f"first, or unset {FLAG}")
        _MODEL_CACHE["scorer"] = CrossEncoder(str(path), device="cpu", max_length=512)
    return _MODEL_CACHE["scorer"]


def _text(passage: dict) -> str:
    """What the cross-encoder reads for one page: the context the prompt would show."""
    return (passage.get("context") or "")[:MAX_CHARS]


def apply(passages: list[dict], question: str, k: int | None = None,
          scorer=None) -> list[dict]:
    """Reorder `passages` by cross-encoder score and keep the best `k`.

    `scorer` takes (question, [texts]) and returns one score per text; it is a parameter so
    the tests can run without loading the model. Ties keep their BM25 order (the sort is
    stable), so the same input always produces the same list. With `anchor()` above zero
    the first that many passages stay where BM25 put them and only the tail is reordered.

    With `enabled()` off this returns its input untouched and loads nothing, so a caller
    that forgets the check still runs the accepted pipeline.
    """
    if not passages or not enabled():
        return passages
    wanted = min(k or len(passages), len(passages))
    keep = min(anchor(), wanted, len(passages) - 1) if len(passages) > 1 else 0
    head = passages[:keep]
    rest = passages[keep:]
    if not rest:
        return passages[:wanted]
    scorer = scorer or predict
    scores = scorer(question, [_text(passage) for passage in rest])
    scored = [dict(passage, rerank=round(float(score), 4), bm25_rank=keep + position)
              for position, (passage, score) in enumerate(zip(rest, scores))]
    ordered = sorted(scored, key=lambda passage: -passage["rerank"])
    return (head + ordered)[:wanted]


def predict(question: str, texts: list[str]) -> list[float]:
    """The shipped scorer: one relevance score per passage text, higher is better."""
    return [float(value) for value in _default_scorer().predict(
        [(question, text) for text in texts], batch_size=len(texts) or 1,
        show_progress_bar=False)]
