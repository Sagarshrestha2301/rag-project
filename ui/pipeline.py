"""The UI's only way to answer: the pipeline the eval measures, with a stream on top.

D-061: the browser must not run a second prompt path. `ui/server.py` had its own system
rules and no router, gate, verifier or cache, so the answers a reader saw were not the
answers `eval/` scored. This module calls `generation.answer` itself -- router,
condensation, cache, retrieval, gate, prompt, verifier and the one retry are all the
shipped code -- and adds exactly two things that cannot change what is scored:

- a token callback, so text reaches the browser while the model writes it, and
- the `debug_version` 1 payload `ui/SPEC.md` section 7 defines.

Nothing here chooses a passage, edits a prompt or repairs an answer.

Usage:
    from ui import pipeline
    for event in pipeline.stream("What was the 24-hour rainfall at Tistung?"):
        event["event"]        # 'start' | 'token' | 'done' | 'error'
        event.get("text")     # a streamed token, on 'token'
        event.get("payload")  # the debug payload, on 'done'

    pipeline.debug_payload(record, index)   # build the payload from a saved record

Example of one finished answer's payload:
    {'debug_version': 1, 'status': 'verified', 'cached': False,
     'route': {'route': 'normal', 'k': 5, ...},
     'retrieval': {'k': 5, 'passages': [{'n': 1, 'rank': 1, 'page': 3, 'score': 18.42}]},
     'gate': {'top': 18.42, 'floor': 15.0, 'decision': 'answer'},
     'verification': {'ok': True, 'verified_quotes': 1, 'citations': [...]},
     'timings_ms': {'retrieval': 41.0, 'model_total': 8600.0, 'total': 8700.0},
     'unreadable': {'corpus': {...}, 'top_documents': [...]},
     'sources': [{'n': 1, 'label': 'Marahatta 1970', 'reference': 'Marahatta & Bhusal
     (2009). Relating Hydrological Extremes with Area. J. Hydrology & Meteorology',
     'doc': '1970_Marahatta_....pdf', 'page': 3, 'snippet': '...'}]}
"""

from __future__ import annotations

import pathlib
import queue
import threading

from generation import answer as generator
from ingest import bibliography

# Bumped when the payload's shape changes, so the view can refuse a shape it does not
# know instead of rendering fields that are not there (ui/SPEC.md section 7).
DEBUG_VERSION = 1

# The evidence rail shows at most this many documents with unreadable pages, then
# "and N more": five lines is what fits before it stops being an explanation (SPEC 7.3).
UNREADABLE_LIST_CAP = 5

# `index/bibliography.json` is read once per process: the rail asks for it on every
# answer, and the file changes only when ingestion runs.
_BIBLIOGRAPHY: dict | None = None


def bibliography_records() -> dict:
    """Document name -> its validated bibliographic record (empty when not extracted)."""
    global _BIBLIOGRAPHY
    if _BIBLIOGRAPHY is None:
        folder = pathlib.Path(__file__).resolve().parent.parent / "index"
        _BIBLIOGRAPHY = bibliography.load(folder).get("documents", {})
    return _BIBLIOGRAPHY


def index() -> dict:
    """The page index, through the pipeline's own loader so both share one object."""
    return generator.index()


def unreadable_summary(source: dict, passages: list[dict]) -> dict:
    """D-021's counts: the corpus totals, plus the retrieved documents that have gaps.

    Every number is computed from `index/pages.json` at request time, never hard-coded,
    so a corpus rebuild updates the warning without a code change. An OCR'd document is
    reported as OCR'd through `ocr_pages` and not counted as unreadable.
    """
    missing = source.get("unreadable") or {}
    corpus = {
        "documents": len(source.get("docs") or {}),
        "pages": len(source.get("pages") or []),
        "documents_with_unreadable": len(missing),
        "unreadable_pages": sum(len(pages) for pages in missing.values()),
        "ocr_pages": int(source.get("ocr_pages") or 0),
    }

    top: list[dict] = []
    for passage in passages:
        doc = passage.get("doc")
        pages = missing.get(doc)
        if not doc or not pages or any(entry["doc"] == doc for entry in top):
            continue
        if len(top) >= UNREADABLE_LIST_CAP:
            break
        top.append({"doc": doc, "label": passage.get("label"), "count": len(pages),
                    "pages": list(pages)})
    return {"corpus": corpus, "top_documents": top}


def sources(passages: list[dict]) -> list[dict]:
    """What the evidence rail lists: one entry per passage the model was shown.

    `reference` is the human-readable citation from `index/bibliography.json` (D-066); the
    file name stays in `doc`, because that is what `/pdf/<name>` opens and what the
    verifier compares against. A document without extracted metadata keeps its label.
    """
    records = bibliography_records()
    out = []
    for passage in passages:
        record = records.get(passage.get("doc")) or {}
        out.append({"n": passage.get("n"), "rank": passage.get("rank"),
                    "doc": passage.get("doc"), "page": passage.get("page"),
                    "label": passage.get("label"), "score": passage.get("score"),
                    "reference": bibliography.reference_line(record) or None,
                    "snippet": passage.get("snippet"), "ocr": bool(passage.get("ocr"))})
    return out


def debug_payload(record: dict, source: dict) -> dict:
    """`debug_version` 1: what happened, in the order it happened (SPEC section 7)."""
    passages = record.get("passages") or []
    listed = [{"n": passage.get("n"), "rank": passage.get("n"),
               "doc": passage.get("doc"), "page": passage.get("page"),
               "label": passage.get("label"), "score": passage.get("score"),
               # No cross-encoder reranker ships: page-level BM25 only (EVAL.md,
               # 2026-11-16). The field exists so the view does not change when one does.
               "rerank_score": None}
              for passage in passages]

    timing = record.get("timing") or {}
    stages = dict(record.get("timings") or {})
    stages["model_total"] = timing.get("total_ms")
    stages["model_ttft"] = timing.get("ttft_ms")
    stages["total"] = round(float(record.get("seconds") or 0.0) * 1000, 1)

    verdict = {"ok": record.get("status") == "verified",
               "said_not_found": record.get("status") == "not_found",
               "verified_quotes": len([c for c in record.get("citations") or []
                                       if c.get("verified", True)]),
               "attempts": record.get("attempts") or 0,
               "citations": [{"n": c.get("n"), "doc": c.get("file") or c.get("file_name"),
                              "page": c.get("page"), "quote": c.get("quote"),
                              "verified": c.get("verified", True)}
                             for c in record.get("citations") or []],
               "problems": list(record.get("problems") or [])}

    route = record.get("route") or {}
    return {
        "debug_version": DEBUG_VERSION,
        "status": record.get("status"),
        "cached": bool(record.get("cached")),
        "question": record.get("question"),
        "search_question": record.get("search_question"),
        "condensed": bool(record.get("condensed")),
        "route": {"route": route.get("route"), "k": route.get("k"),
                  "prompt_mode": route.get("prompt_mode"),
                  "condense": route.get("condense"), "reason": route.get("reason")},
        "model": {"name": record.get("model"), "digest": generator.model_digest(
            record.get("model") or generator.MODEL),
            "prompt_version": record.get("prompt_version"),
            "num_ctx": generator.NUM_CTX, "temperature": generator.TEMPERATURE},
        "retrieval": {"k": len(listed), "passages": listed},
        "gate": dict(record.get("gate") or {}),
        "verification": verdict,
        "timings_ms": stages,
        "tokens": {"prompt": timing.get("prompt_tokens"),
                   "answer": timing.get("answer_tokens")},
        "unreadable": unreadable_summary(source, passages),
        "sources": sources(passages),
        "answer": record.get("answer") or "",
        "error": None,
    }


def stream(question: str, history: list[dict] | None = None, *,
           source: dict | None = None, use_cache: bool = True):
    """Yield `start`, then `token` events, then one `done` or `error`.

    `generation.answer` is synchronous and the model call blocks, so it runs in one
    worker thread and hands tokens back through a queue. Stopping the browser request
    does not cancel the model immediately -- Ollama has no cancel -- so the thread is a
    daemon and its result is simply dropped.
    """
    page_index = source if source is not None else index()
    events: queue.Queue = queue.Queue()
    box: dict = {}

    def on_token(text: str) -> None:
        events.put(("token", text))

    def work() -> None:
        try:
            box["record"] = generator.answer(question, index=page_index, history=history,
                                             use_cache=use_cache, on_token=on_token)
        except Exception as exc:  # noqa: BLE001 - the browser must see any failure
            box["error"] = f"{exc.__class__.__name__}: {exc}"
        finally:
            events.put(("end", None))

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    yield {"event": "start", "question": question,
           "model": {"name": generator.MODEL, "num_ctx": generator.NUM_CTX,
                     "prompt_version": generator.prompt.PROMPT_VERSION,
                     "temperature": generator.TEMPERATURE}}

    while True:
        kind, value = events.get()
        if kind == "end":
            break
        yield {"event": kind, "text": value}

    worker.join(timeout=5)
    if "error" in box:
        yield {"event": "error", "message": box["error"]}
        return
    yield {"event": "done", "payload": debug_payload(box["record"], page_index)}


def pdf_path(name: str) -> pathlib.Path | None:
    """Resolve a citation's file name to a corpus PDF, subfolders included.

    Kept here beside the payload so the link a chip opens and the page the payload names
    are resolved by one function, not two (92 of 97 PDFs sit below `data/corpus/`).
    """
    from corpus import CORPUS

    if not name or "/" in name or "\\" in name:
        return None
    for path in CORPUS.rglob(name):
        if path.is_file() and CORPUS in path.resolve().parents:
            return path.resolve()
    return None
