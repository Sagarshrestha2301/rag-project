"""Prove the routes: the page, the CSP, the PDF resolution and the chat event stream.

The model is never called. `ui.pipeline.stream` is replaced with a stub that yields the
four events the server relays, so what is tested is transport and routing.

Usage:
    .venv\\Scripts\\python.exe ui\\test_server.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from corpus import CORPUS  # noqa: E402
from ui import pipeline, server  # noqa: E402

CLIENT = TestClient(server.app)

EVENTS = [
    {"event": "start", "model": {"name": "qwen3.5:4b"}},
    {"event": "token", "text": "540 mm "},
    {"event": "token", "text": "fell [1]."},
    {"event": "done", "payload": {"debug_version": 1, "status": "verified",
                                  "answer": "540 mm fell [1].", "sources": [
                                      {"n": 1, "doc": "a.pdf", "page": 3, "label": "A",
                                       "score": 18.42, "snippet": "540 mm", "ocr": False}]}},
]


def stub_stream(question, history=None, **kwargs):
    """What pipeline.stream yields, without a model."""
    yield from EVENTS


def page_is_served_with_the_policy() -> None:
    """The shell loads and the browser is told it may not reach anything but us."""
    response = CLIENT.get("/")
    assert response.status_code == 200, response.status_code
    assert 'data-action="show-tab"' in response.text, "the evidence tabs must be in the shell"
    policy = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in policy, policy
    assert "connect-src 'self'" in policy, "the browser must not be able to call Ollama"


def every_asset_is_local() -> None:
    """No CDN, no webfont: every src and href in the shell is same-origin."""
    html = CLIENT.get("/").text
    for needle in ("<script src=\"/static/", "href=\"/static/"):
        assert needle in html, needle
    assert "http://" not in html and "https://" not in html, "an external URL in the shell"


def static_files_exist() -> None:
    """app.js and step7.css are reachable, so a typo cannot ship a blank page."""
    for name in ("app.js", "app.css", "step7.css"):
        response = CLIENT.get(f"/static/{name}")
        assert response.status_code == 200, (name, response.status_code)
        assert response.content, f"{name} is empty"


def pdf_resolves_across_subfolders() -> None:
    """92 of 97 PDFs sit below data/corpus, and their citations must still open."""
    name = next(path.name for path in CORPUS.rglob("*.pdf"))
    response = CLIENT.get(f"/pdf/{name}")
    assert response.status_code == 200, response.status_code
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers.get("content-disposition", "")


def pdf_refuses_anything_outside_the_corpus() -> None:
    """A name that is not a corpus document, or tries to walk out, is a 404."""
    for name in ("nope.pdf", "..%2Frequirements.txt", "..%2F..%2FAGENTS.md"):
        response = CLIENT.get(f"/pdf/{name}")
        assert response.status_code == 404, (name, response.status_code)


def chat_streams_events_in_order() -> None:
    """The browser gets start, tokens, done -- and the payload it renders."""
    original = pipeline.stream
    server.pipeline.stream = stub_stream
    try:
        response = CLIENT.post("/api/chat", json={
            "messages": [{"role": "user", "content": "What was the rainfall?"}]})
    finally:
        server.pipeline.stream = original

    assert response.status_code == 200, response.status_code
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert [event["event"] for event in events] == ["start", "token", "token", "done"], events
    assert events[-1]["payload"]["status"] == "verified"
    assert "no-store" in response.headers.get("cache-control", "")


def chat_sends_history_but_not_the_question_twice() -> None:
    """`history` is the turns before this one, so a follow-up can be condensed."""
    seen = {}

    def capture(question, history=None, **kwargs):
        seen["question"] = question
        seen["history"] = history
        yield from EVENTS

    original = pipeline.stream
    server.pipeline.stream = capture
    try:
        CLIENT.post("/api/chat", json={"messages": [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "and in 1990?"},
        ]})
    finally:
        server.pipeline.stream = original

    assert seen["question"] == "and in 1990?", seen
    assert [m["content"] for m in seen["history"]] == ["first", "answer"], seen["history"]


def health_reports_the_index() -> None:
    """The header badge and the D-021 counts come from the real index, not constants."""
    data = CLIENT.get("/api/health").json()
    assert data["model"], data
    for key in ("pages", "documents", "ocr_pages", "unreadable"):
        assert key in data, f"missing {key}"
    config = CLIENT.get("/api/config").json()
    assert config["pages"] == data["pages"], "one source of truth for the page count"


CASES = [
    ("the shell is served with a CSP", page_is_served_with_the_policy),
    ("every asset is same-origin", every_asset_is_local),
    ("app.js, app.css and step7.css load", static_files_exist),
    ("a subfoldered corpus PDF opens", pdf_resolves_across_subfolders),
    ("a non-corpus path is refused", pdf_refuses_anything_outside_the_corpus),
    ("chat streams start, tokens, done", chat_streams_events_in_order),
    ("history is sent, the question once", chat_sends_history_but_not_the_question_twice),
    ("health reports the index", health_reports_the_index),
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
