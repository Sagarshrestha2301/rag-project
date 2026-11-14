"""Oracle test for the generator (Step 2 task 4).

Gives the model the gold page text for every eval question — perfect retrieval —
and writes a run file in the format `eval/score.py` reads. What it measures is
answer quality alone: does the model answer, does it refuse when the answer is
absent, does it quote a sentence that really exists on the page.

The model is asked for a short answer plus one verbatim sentence, so the
citation check in the scorer verifies a real quote rather than a page number the
harness supplied.

The server is Ollama (default port 11434), which exposes an OpenAI-compatible
endpoint, so the request shape is unchanged since the llama.cpp era.

Usage (Ollama must already be running):
    .venv\\Scripts\\python.exe benchmarks/llm/oracle_run.py --out benchmarks/llm/oracle-qwen2.5-7b.jsonl
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
import urllib.request

import pymupdf

QUESTIONS = pathlib.Path("eval/questions.jsonl")
MAX_PAGE_CHARS = 6000

SYSTEM = (
    "You answer questions about documents. Use only the context given. "
    "If the context does not contain the answer, reply exactly: NOT FOUND. "
    "Otherwise reply in exactly this form, with the quote copied verbatim from the context:\n"
    "ANSWER: <the answer>\nQUOTE: <one sentence copied from the context>"
)


def page_text(path: str, page: int) -> str:
    with pymupdf.open(path) as doc:
        return doc[page - 1].get_text()[:MAX_PAGE_CHARS]


def ask(port: int, question: str, context: str, model: str = "qwen2.5",
        no_think: bool = False) -> tuple[str, dict]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
    if no_think:
        # Thinking models spend the answer budget on hidden reasoning: qwen3.5
        # burned 400 tokens and returned an empty string, which the scorer reads
        # as NOT FOUND. Disable it so the model is judged on its answers, and
        # record the flag with the result.
        payload = {"model": model, "stream": False, "think": False,
                   "options": {"temperature": 0, "num_predict": 220},
                   "messages": messages}
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.load(resp)
        usage = {"prompt_tokens": body.get("prompt_eval_count"),
                 "completion_tokens": body.get("eval_count")}
        return (body.get("message") or {}).get("content", ""), {
            "seconds": round(time.perf_counter() - started, 2), "usage": usage}

    payload = {"model": model, "temperature": 0, "max_tokens": 220, "messages": messages}
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.load(resp)
    return body["choices"][0]["message"]["content"], {"seconds": round(time.perf_counter() - started, 2),
                                                      "usage": body.get("usage")}


def parse(reply: str) -> tuple[str, str | None]:
    text = reply.strip()
    answer = re.search(r"(?is)^\s*ANSWER\s*:\s*(.+?)(?:\n\s*QUOTE\s*:|\Z)", text)
    quote = re.search(r"(?is)QUOTE\s*:\s*(.+)\Z", text)
    if not answer and not quote:
        if "NOT FOUND" in text.upper():
            return "", None
        return text, None
    return (answer.group(1).strip() if answer else text), (quote.group(1).strip() if quote else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--model", default="qwen2.5")
    ap.add_argument("--no-think", action="store_true",
                    help="disable reasoning for thinking models (native /api/chat)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    questions = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for i, q in enumerate(questions, start=1):
            src = q["gold_sources"][0]
            context = page_text(src["file"], src["page"])
            reply, timing = ask(args.port, q["question"], context, args.model, args.no_think)
            answer, quote = parse(reply)

            said_not_found = not answer.strip() or "NOT FOUND" in answer.upper()
            row = {
                "id": q["id"],
                "retrieved": [{"file": src["file"], "page": src["page"], "score": 1.0}],
                "answer": "" if said_not_found else answer,
                "citations": [] if (said_not_found or not quote) else
                             [{"file": src["file"], "page": src["page"], "quote": quote}],
                "said_not_found": said_not_found,
                "timings": timing,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[{i:2d}/{len(questions)}] {q['id']} {q['type']:<10} "
                  f"{timing['seconds']:>6.1f}s  {'NOT FOUND' if said_not_found else answer[:60]!r}", flush=True)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
