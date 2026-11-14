"""One 2-line context per document, generated once by the local model (Step 4 task 4).

The context says what the document is about, in two lines, and is stored with
the document rather than repeated in every chunk. The prompt and the model name
are recorded next to each line, so a later run can be compared or regenerated.

Determinism: temperature 0, `think: false` (the pinned qwen3.5 otherwise spends
its budget on hidden reasoning), and a cache that skips documents already done.

Usage (Ollama must be running):
    .venv\\Scripts\\python.exe -m chunk.doc_context --model qwen3.5:4b
    # then, in a build:
    from chunk.doc_context import load
    contexts = load()          # {file: {"context": ..., "model": ..., "prompt": ...}}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request

PARSED = pathlib.Path("index/parsed/pages.jsonl")
CACHE = pathlib.Path("index/doc-context.json")
MAX_INPUT_CHARS = 2500
MAX_OUTPUT_TOKENS = 90

PROMPT = (
    "Describe in exactly two lines what this document is about: its subject, "
    "place or dataset, and study period if stated. Use only the text given; do "
    "not guess a title, author, number or date that is not there. No preamble."
)


def first_pages(pages: list[dict], limit: int = MAX_INPUT_CHARS) -> str:
    """The opening of a document: page 1, then page 2 if page 1 is short."""
    text = ""
    for page in pages[:2]:
        text += page.get("text", "") + "\n"
        if len(text) >= limit:
            break
    return text[:limit]


def generate(opening: str, model: str, port: int = 11434) -> str:
    """Ask the local model for the two-line context, temperature 0."""
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": MAX_OUTPUT_TOKENS},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": opening},
        ],
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.load(response)
    return ((body.get("message") or {}).get("content") or "").strip()


def load(cache: pathlib.Path = CACHE) -> dict[str, dict]:
    if not cache.exists():
        return {}
    return json.loads(cache.read_text(encoding="utf-8"))


def build(model: str, port: int = 11434, ask=generate,
          parsed: pathlib.Path = PARSED, cache: pathlib.Path = CACHE) -> dict[str, dict]:
    """Fill the cache for every document that does not have a context yet."""
    docs: dict[str, list[dict]] = {}
    for line in parsed.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            docs.setdefault(record["doc"], []).append(record)
    for pages in docs.values():
        pages.sort(key=lambda page: page["pdf_page"])

    done = load(cache)
    prompt_sha = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()[:16]
    for number, (doc, pages) in enumerate(sorted(docs.items()), start=1):
        if done.get(doc, {}).get("model") == model and done[doc].get("prompt") == prompt_sha:
            continue
        print(f"[{number}/{len(docs)}] {doc[:60]}")
        context = " ".join(ask(first_pages(pages), model, port).split())
        done[doc] = {"context": context, "model": model, "prompt": prompt_sha,
                     "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(done, indent=2, ensure_ascii=False), encoding="utf-8")

    missing = [doc for doc in docs if doc not in done]
    if missing:
        raise RuntimeError(f"{len(missing)} documents still have no context, e.g. {missing[:3]}")
    return {doc: done[doc] for doc in docs}


def main() -> int:
    parser = argparse.ArgumentParser(prog="chunk.doc_context")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args()
    contexts = build(args.model, args.port)
    print(f"{len(contexts)} document contexts in {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
