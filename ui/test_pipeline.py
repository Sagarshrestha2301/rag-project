"""Prove the wrapper: payload shape, D-021 counts, and the event stream's order.

No model, no network, no browser: `generation.answer` is replaced with a stub that calls
the token callback exactly as the real one does, so what is tested is this module's own
behaviour rather than Ollama's.

Usage:
    .venv\\Scripts\\python.exe ui\\test_pipeline.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui import pipeline  # noqa: E402


INDEX = {
    "docs": {"a.pdf": {}, "b.pdf": {}, "c.pdf": {}},
    "pages": [{"doc": "a.pdf", "page": 1}, {"doc": "b.pdf", "page": 1},
              {"doc": "c.pdf", "page": 1}],
    "unreadable": {"a.pdf": [1, 2, 3], "b.pdf": [4]},
    "ocr_pages": 5,
}

RECORD = {
    "question": "q", "search_question": "q", "condensed": False, "cached": False,
    "status": "verified", "answer": "540 mm fell [1].",
    "model": "qwen3.5:4b", "prompt_version": "s6-2", "seconds": 8.7,
    "route": {"route": "normal", "k": 5, "prompt_mode": "normal", "condense": False,
              "reason": "no rule matched"},
    "gate": {"top": 18.42, "floor": 15.0, "refused": False, "decision": "answer",
             "reason": "the model decides"},
    "passages": [{"n": 1, "doc": "a.pdf", "page": 3, "label": "A · paper",
                  "score": 18.42, "snippet": "540 mm", "ocr": False}],
    "citations": [{"n": 1, "file": "a.pdf", "page": 3, "quote": "540 mm", "verified": True}],
    "problems": [], "attempts": 1,
    "timing": {"total_ms": 8600.0, "ttft_ms": 6200.0, "prompt_tokens": 1818,
               "answer_tokens": 104},
    "timings": {"route": 0.1, "retrieval": 41.0, "verify": 38.0, "total": 8700.0},
}


def payload_has_the_spec_shape() -> None:
    """Every field ui/SPEC.md section 7.1 names is present, and nothing invents a number."""
    data = pipeline.debug_payload(RECORD, INDEX)
    assert data["debug_version"] == pipeline.DEBUG_VERSION, data.get("debug_version")
    for key in ("status", "cached", "question", "search_question", "condensed", "route",
                "model", "retrieval", "gate", "verification", "timings_ms", "tokens",
                "unreadable", "sources", "answer", "error"):
        assert key in data, f"missing {key}"
    assert data["retrieval"]["passages"][0]["rank"] == 1, "rank is list order"
    assert data["retrieval"]["passages"][0]["rerank_score"] is None, \
        "no reranker ships, so the field must be null rather than a made-up score"
    assert data["verification"]["verified_quotes"] == 1
    assert data["timings_ms"]["model_total"] == 8600.0, "Ollama's own counter"
    assert data["timings_ms"]["total"] == 8700.0, "record seconds x 1000"
    assert data["tokens"] == {"prompt": 1818, "answer": 104}
    assert data["sources"][0]["snippet"] == "540 mm", "the rail needs the page snippet"


def unreadable_counts_match_the_index() -> None:
    """D-021's numbers come from the index, not from constants in the view."""
    data = pipeline.debug_payload(RECORD, INDEX)
    corpus = data["unreadable"]["corpus"]
    assert corpus["documents"] == 3, corpus
    assert corpus["pages"] == 3, corpus
    assert corpus["documents_with_unreadable"] == 2, corpus
    assert corpus["unreadable_pages"] == 4, "3 pages in a.pdf plus 1 in b.pdf"
    assert corpus["ocr_pages"] == 5
    top = data["unreadable"]["top_documents"]
    assert [entry["doc"] for entry in top] == ["a.pdf"], \
        "only retrieved documents are named"
    assert top[0]["pages"] == [1, 2, 3], top


def unreadable_list_is_capped_and_deduplicated() -> None:
    """Five document lines, then the rest is summarised by the corpus line."""
    passages = [{"doc": f"{name}.pdf", "page": 1, "label": name, "n": i}
                for i, name in enumerate(["a", "b", "c", "d", "e", "f"], start=1)]
    index = {"docs": {}, "pages": [], "ocr_pages": 0,
             "unreadable": {f"{name}.pdf": [1] for name in "abcdef"}}
    summary = pipeline.unreadable_summary(index, passages)
    assert len(summary["top_documents"]) == pipeline.UNREADABLE_LIST_CAP, \
        summary["top_documents"]
    assert len({entry["doc"] for entry in summary["top_documents"]}) == 5, "no duplicates"


def stream_yields_start_tokens_done(monkeypatch=None) -> None:
    """Order matters: no token before start, no payload before the last token."""
    original = pipeline.generator.answer
    seen = {}

    def stub(question, **kwargs):
        seen["history"] = kwargs.get("history")
        seen["use_cache"] = kwargs.get("use_cache")
        kwargs["on_token"]("540 mm ")
        kwargs["on_token"]("fell [1].")
        return dict(RECORD)

    pipeline.generator.answer = stub
    try:
        events = list(pipeline.stream("q", [{"role": "user", "content": "earlier"}],
                                       source=INDEX, use_cache=False))
    finally:
        pipeline.generator.answer = original

    kinds = [event["event"] for event in events]
    assert kinds == ["start", "token", "token", "done"], kinds
    assert "".join(e["text"] for e in events if e["event"] == "token") == "540 mm fell [1]."
    assert events[-1]["payload"]["status"] == "verified"
    assert seen["use_cache"] is False and seen["history"], "history must reach the pipeline"


def stream_reports_a_failure_as_an_event() -> None:
    """A crash becomes one `error` event, not a stack trace in the browser console."""
    original = pipeline.generator.answer

    def stub(question, **kwargs):
        raise RuntimeError("Ollama 500: model not loaded")

    pipeline.generator.answer = stub
    try:
        events = list(pipeline.stream("q", source=INDEX))
    finally:
        pipeline.generator.answer = original
    assert [event["event"] for event in events] == ["start", "error"], events
    assert "model not loaded" in events[-1]["message"], events[-1]


def a_greeting_has_no_sources() -> None:
    """`greeting` is a rule, not a sixth state: no lookup, no chips, no sources."""
    record = dict(RECORD, status="greeting", passages=[], citations=[], answer="Hello.")
    data = pipeline.debug_payload(record, INDEX)
    assert data["sources"] == [] and data["retrieval"]["passages"] == []
    assert data["verification"]["verified_quotes"] == 0


CASES = [
    ("payload carries every field the spec names", payload_has_the_spec_shape),
    ("unreadable counts come from the index", unreadable_counts_match_the_index),
    ("the unreadable list is capped and deduplicated", unreadable_list_is_capped_and_deduplicated),
    ("the stream is start, tokens, done", stream_yields_start_tokens_done),
    ("a failure is an error event", stream_reports_a_failure_as_an_event),
    ("a greeting offers no sources", a_greeting_has_no_sources),
]


def main() -> int:
    failed = 0
    for name, case in CASES:
        try:
            case()
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {name}: {exc}")
        else:
            print(f"  PASS  {name}")
    print(f"\n{'all' if not failed else failed} "
          f"{'cases pass' if not failed else 'case(s) failed'} ({len(CASES)} total)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
