"""Open the citation link the UI builds, for 10 tested answers, and check the page.

The Step 7 box this proves: "Citation click opens the right PDF page for 10 tested
answers". A chip renders `[n]` and points at `/pdf/<file name>#page=<n>` (app.js
`openSource`). This script asks the questions through the running server, takes each
answer's verified citations from the `done` payload the UI renders, then fetches the
exact URL the chip would open, parses the PDF bytes the server sends, and checks that
the cited page carries the quoted sentence.

It is the served bytes that are read, not `data/corpus`, so a wrong file or a wrong
page in the server's resolver fails here even though the page exists on disk. The
comparison is `generation.verify.norm`, the same rule the answer verifier uses: the
quotation has to be on the page, character for character apart from whitespace.

Usage:
    .venv\\Scripts\\python.exe scripts\\verify-citation-links.py [http://127.0.0.1:8000] [--run <run.jsonl>]

Example of one line of output:
    q001  [1] Marahatta…_W2121362616.pdf p.2  HTTP 200   quote on page: yes
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

from generation.verify import norm  # noqa: E402

DEFAULT_SERVER = "http://127.0.0.1:8000"
DEFAULT_RUN = ROOT / "eval" / "runs" / "2026-11-18-step6-after-ui" / "run.jsonl"
QUESTIONS = ROOT / "eval" / "questions.jsonl"
OUT = ROOT / "artifacts" / "step7" / "citation-clickthrough.json"
ANSWERS = 10


def question_text() -> dict[str, str]:
    """{id: question} from the eval set, which is the only place the wording lives."""
    return {record["id"]: record["question"]
            for record in (json.loads(line) for line in
                           QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip())}


def chosen_ids(run: pathlib.Path) -> list[str]:
    """Ten answers, spread over documents before topping up.

    Document diversity matters here: 92 of the 97 PDFs sit in subfolders of
    `data/corpus`, so a sample from one document would not exercise the resolver the
    chips depend on.
    """
    rows = [json.loads(line) for line in run.read_text(encoding="utf-8").splitlines() if line.strip()]
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        docs = {c.get("file") for c in row.get("citations") or []}
        if docs - seen:
            ordered.append(row["id"])
            seen |= docs
    for row in rows:
        if row.get("citations") and row["id"] not in ordered:
            ordered.append(row["id"])
    return ordered[:ANSWERS]


def ask(server: str, question: str) -> dict:
    """POST one question and return the `done` payload, the same object the UI renders."""
    body = json.dumps({"messages": [{"role": "user", "content": question}]}).encode()
    request = urllib.request.Request(f"{server}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    payload = None
    with urllib.request.urlopen(request, timeout=300) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            event = json.loads(line)
            if event["event"] == "done":
                payload = event["payload"]
            elif event["event"] == "error":
                raise RuntimeError(event["message"])
    if payload is None:
        raise RuntimeError("stream ended without a done event")
    return payload


def fetch(server: str, doc: str, page: int) -> tuple[int, str, bytes]:
    """GET the chip's URL exactly as the browser builds it, fragment removed by HTTP."""
    path = "/pdf/" + urllib.parse.quote(doc, safe="")
    request = urllib.request.Request(server + path)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.headers.get("content-type", ""), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), b""


def page_text(pdf_bytes: bytes, page: int) -> str:
    """One page of the served PDF, as the reader who clicks the chip would see it."""
    with pymupdf.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as pdf:
        if not 1 <= page <= pdf.page_count:
            return ""
        return pdf[page - 1].get_text()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="verify-citation-links")
    parser.add_argument("server", nargs="?", default=DEFAULT_SERVER)
    parser.add_argument("--run", default=str(DEFAULT_RUN),
                        help="recorded run whose questions are re-asked through the UI")
    args = parser.parse_args(argv)

    ids = chosen_ids(pathlib.Path(args.run))
    wording = question_text()
    results: list[dict] = []
    failures = 0

    for number, question_id in enumerate(ids, start=1):
        question = wording[question_id]
        payload = ask(args.server, question)
        citations = [c for c in (payload.get("verification") or {}).get("citations") or []
                     if c.get("verified")]
        if not citations:
            failures += 1
            results.append({"id": question_id, "question": question, "error": "no verified citation",
                            "status": payload.get("status")})
            print(f"{question_id}  FAILED: status={payload.get('status')}, no verified citation")
            continue

        for citation in citations:
            doc = citation.get("doc") or ""
            page = int(citation.get("page") or 0)
            quote = citation.get("quote") or ""
            status, kind, body = fetch(args.server, doc, page)
            served_ok = status == 200 and kind.startswith("application/pdf")
            text = page_text(body, page) if served_ok else ""
            found = bool(quote) and norm(quote) in norm(text)
            ok = served_ok and found
            failures += 0 if ok else 1
            results.append({
                "id": question_id, "n": citation.get("n"), "doc": doc, "page": page,
                "chip_url": "/pdf/" + urllib.parse.quote(doc, safe="") + f"#page={page}",
                "http_status": status, "content_type": kind, "quote": quote,
                "quote_on_page": found, "page_chars": len(text), "ok": ok,
            })
            head = doc[:44] + ("…" if len(doc) > 44 else "")
            print(f"{question_id}  [{citation.get('n')}] {head} p.{page}  HTTP {status}  "
                  f"quote on page: {'yes' if found else 'NO'}"
                  f"{'' if served_ok else '  (not a served PDF)'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"answers": len(ids), "checks": results}, indent=1), encoding="utf-8")
    checks = [c for c in results if "ok" in c]
    print(f"\nanswers checked: {len(ids)}, citation links checked: {len(checks)}, "
          f"failures: {failures}")
    print(f"verdict: {'PASS' if failures == 0 else 'FAIL'}  ({OUT})")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
