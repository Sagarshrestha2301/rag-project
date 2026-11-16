"""Answer one question: retrieve, prompt, ask the local model, verify the quotes.

The loop this implements is the Step 6 contract: an answer is only returned as
verified when every quotation in it is on the page it cites. If verification fails,
the model is told what failed and asked once more; if the second answer fails too, it
is returned marked `unverified` with the reasons, never silently passed off as
grounded.

This is tasks 1 and 2 of Step 6. The not-found gate (task 3, D-058), the intent router
(task 4), the condense step (task 5) and the cache (task 6) are not here yet, so a
refusal is recognised but not yet decided by a threshold.

Usage:
    .venv\\Scripts\\python.exe -m generation.answer "What was the 24-hour rainfall at Tistung?"
    .venv\\Scripts\\python.exe -m generation.answer "..." --json     # full record
    .venv\\Scripts\\python.exe -m generation.answer "..." --k 6      # 4-6 passages

Environment: OLLAMA_URL, CHAT_MODEL, CHAT_NUM_CTX, CHAT_KEEP_ALIVE, CHAT_THINK.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

from generation import prompt, think, verify
from ui import retrieval

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("CHAT_MODEL", "qwen3.5:4b")
NUM_CTX = int(os.environ.get("CHAT_NUM_CTX", "4096"))
KEEP_ALIVE = os.environ.get("CHAT_KEEP_ALIVE", "30m")
# Thinking stays off: with it on, qwen3.5 spends the answer budget on hidden reasoning
# and returns an empty string (measured on all 30 questions in Step 2).
THINK = os.environ.get("CHAT_THINK", "0").lower() in ("1", "true", "yes")
PASSAGES = 5          # Step 6 asks for 4-6; five fits 4096 tokens with room to answer

_INDEX: dict | None = None


def index() -> dict:
    """The page index, built once per process (cached on disk by ui.retrieval)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = retrieval.build()
    return _INDEX


def _ask(messages: list[dict], model: str, temperature: float = 0.0) -> tuple[str, dict]:
    """One non-streamed call. Returns the cleaned text and the timing Ollama reports."""
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": THINK,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature, "num_ctx": NUM_CTX},
    }
    with httpx.Client(timeout=httpx.Timeout(connect=5, read=600, write=30, pool=5)) as client:
        response = client.post(f"{OLLAMA_URL}/api/chat", json=body)
        if response.status_code != 200:
            raise RuntimeError(f"Ollama {response.status_code}: {response.text[:300]}")
        payload = response.json()
    text = think.strip((payload.get("message") or {}).get("content") or "")
    timing = {
        "total_ms": round((payload.get("total_duration") or 0) / 1e6, 1),
        "load_ms": round((payload.get("load_duration") or 0) / 1e6, 1),
        "ttft_ms": round((payload.get("prompt_eval_duration") or 0) / 1e6, 1),
        "prompt_tokens": payload.get("prompt_eval_count"),
        "answer_tokens": payload.get("eval_count"),
    }
    return text, timing


def answer(question: str, *, k: int = PASSAGES, model: str = MODEL,
           index: dict | None = None, temperature: float = 0.0) -> dict:
    """Retrieve, ask, verify, retry once if the quotes do not check out.

    Returns a record with the answer, its citations, the verification verdict, how many
    attempts it took, and the passages that were shown — everything the eval needs and
    nothing inferred.
    """
    started = time.perf_counter()
    source = index if index is not None else globals()["index"]()
    passages = retrieval.search(source, question, k=k)

    messages = [{"role": "system", "content": prompt.build_system(passages)},
                {"role": "user", "content": question}]
    text, timing = _ask(messages, model, temperature)
    verdict = verify.verify_answer(text, passages)
    attempts = 1

    # D-010: a failed answer is retried once. A refusal is not a failure — the model
    # read the passages and said they do not contain the answer.
    if not verdict["ok"] and not verdict["said_not_found"] and verdict["problems"]:
        messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": prompt.retry_message(verdict["problems"])},
        ]
        text, timing = _ask(messages, model, temperature)
        verdict = verify.verify_answer(text, passages)
        attempts = 2

    if verdict["said_not_found"] and verdict["ok"]:
        status = "not_found"
    elif verdict["ok"]:
        status = "verified"
    else:
        status = "unverified"

    return {
        "question": question,
        "answer": text,
        "status": status,
        "citations": verdict["citations"],
        "problems": verdict["problems"],
        "attempts": attempts,
        "passages": [{"n": i, "doc": p.get("doc"), "page": p["page"],
                      "label": p.get("label"), "score": p.get("score")}
                     for i, p in enumerate(passages, start=1)],
        "model": model,
        "prompt_version": prompt.PROMPT_VERSION,
        "timing": timing,
        "seconds": round(time.perf_counter() - started, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generation.answer", description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=PASSAGES, help="passages in context (4-6)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--json", action="store_true", help="print the whole record")
    args = parser.parse_args(argv)

    record = answer(args.question, k=args.k, model=args.model)
    if args.json:
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] != "unverified" else 1

    print(f"Q: {record['question']}")
    print(f"model {record['model']} | {record['seconds']} s | attempts {record['attempts']} "
          f"| prompt {record['prompt_version']}")
    print()
    print(record["answer"] or "(empty answer)")
    print()
    print(f"status: {record['status']}")
    for problem in record["problems"]:
        print(f"  - {problem}")
    if record["citations"]:
        print("citations:")
        for citation in record["citations"]:
            print(f"  [{citation['n']}] {citation['file']}, p. {citation['page']}")
    return 0 if record["status"] != "unverified" else 1


if __name__ == "__main__":
    sys.exit(main())
