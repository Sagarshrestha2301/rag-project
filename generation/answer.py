"""Answer one question: retrieve, prompt, ask the local model, verify the quotes.

The loop this implements is the Step 6 contract: an answer is only returned as
verified when every quotation in it is on the page it cites. If verification fails,
the model is told what failed and asked once more; if the second answer fails too, it
is returned marked `unverified` with the reasons, never silently passed off as
grounded.

This is tasks 1-6 of Step 6. The router (`generation/router.py`) decides the route and
its retrieval/prompt settings, the condense step (`generation/condense.py`) rewrites a
follow-up only when there is history, the gate (`generation/gate.py`, D-058) refuses on a
floor or on the model's own refusal, and the cache (`generation/cache.py`, D-017) is keyed
on the question, the index, the model file and the prompt version. Task 7 runs all of it
over the eval set: `eval/run_generation.py`.

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
import pathlib
import sys
import time
from collections.abc import Callable

import httpx

from corpus import build as build_pages, search as search_pages
from generation import cache, condense, gate, prompt, router, think, verify

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("CHAT_MODEL", "qwen3.5:4b")
NUM_CTX = int(os.environ.get("CHAT_NUM_CTX", "4096"))
KEEP_ALIVE = os.environ.get("CHAT_KEEP_ALIVE", "30m")
# Temperature 0 makes sampling greedy, and the seed is pinned anyway (EVAL.md run
# protocol): a later Ollama default must not be able to make two eval runs incomparable.
SEED = int(os.environ.get("CHAT_SEED", "0"))
# Thinking stays off: with it on, qwen3.5 spends the answer budget on hidden reasoning
# and returns an empty string (measured on all 30 questions in Step 2).
THINK = os.environ.get("CHAT_THINK", "0").lower() in ("1", "true", "yes")
# Named so the debug payload can report it (ui/SPEC.md 7.1) and so the CLI, the eval and
# the UI cannot drift apart on the one setting that decides reproducibility.
TEMPERATURE = 0.0
GREETING_REPLY = ("Hello. Ask me about the indexed documents — rainfall, floods, land use "
                  "and the reports in the corpus.")

_INDEX: dict | None = None


def index() -> dict:
    """The page index, built once per process (cached on disk by corpus.build)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = build_pages()
    return _INDEX


def _timing(payload: dict) -> dict:
    """Ollama's own counters, in the shape the record and the debug payload read."""
    return {
        "total_ms": round((payload.get("total_duration") or 0) / 1e6, 1),
        "load_ms": round((payload.get("load_duration") or 0) / 1e6, 1),
        "ttft_ms": round((payload.get("prompt_eval_duration") or 0) / 1e6, 1),
        "prompt_tokens": payload.get("prompt_eval_count"),
        "answer_tokens": payload.get("eval_count"),
    }


def _ask(messages: list[dict], model: str, temperature: float = TEMPERATURE,
         on_token: Callable[[str], None] | None = None) -> tuple[str, dict]:
    """One call. Returns the cleaned text and the timing Ollama reports.

    Without `on_token` this is the non-streamed call the eval makes, byte for byte as it
    was: same body, same options, same seed. With `on_token` the same request is sent
    with `stream: true` and each cleaned piece is handed to the caller as it arrives, so
    the UI shows the model writing rather than a copy of this function writing.
    """
    body = {
        "model": model,
        "messages": messages,
        "stream": on_token is not None,
        "think": THINK,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature, "num_ctx": NUM_CTX, "seed": SEED},
    }
    timeout = httpx.Timeout(connect=5, read=600, write=30, pool=5)

    if on_token is None:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{OLLAMA_URL}/api/chat", json=body)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama {response.status_code}: {response.text[:300]}")
            payload = response.json()
        return think.strip((payload.get("message") or {}).get("content") or ""), _timing(payload)

    # A tag can arrive split across two chunks, so the same filter the UI prototype used
    # stands between the model and the reader (generation/think.py).
    pieces: list[str] = []
    timing: dict = {}
    cleaner = think.ThinkFilter()
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=body) as response:
            if response.status_code != 200:
                detail = response.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"Ollama {response.status_code}: {detail}")
            for line in response.iter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                cleaned = cleaner.feed((chunk.get("message") or {}).get("content") or "")
                if cleaned:
                    pieces.append(cleaned)
                    on_token(cleaned)
                if chunk.get("done"):
                    tail = cleaner.flush()
                    if tail:
                        pieces.append(tail)
                        on_token(tail)
                    timing = _timing(chunk)
    return "".join(pieces), timing


def model_digest(model: str) -> str | None:
    """Ollama's digest for a model tag, so the cache key follows the weights (D-017)."""
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=2, read=5, write=5, pool=2)) as client:
            tags = client.get(f"{OLLAMA_URL}/api/tags").json()
    except (httpx.HTTPError, ValueError):
        return None
    for entry in tags.get("models", []):
        name = entry.get("name", "")
        if name == model or name.split(":")[0] == model.split(":")[0]:
            return entry.get("digest")
    return None


def _passages(passages: list[dict]) -> list[dict]:
    """The public shape of the passages that were shown, numbered as the prompt numbered them.

    Both answer paths record this -- the floor refusal and the answered case -- so it is
    built here once. The `n` must match the [n] the model was given, which is why the
    numbering comes from `enumerate` rather than from the order they happen to be found in.
    """
    return [{"n": number, "doc": p.get("doc"), "page": p["page"],
             "label": p.get("label"), "score": p.get("score"),
             # The evidence rail shows the snippet and marks an OCR'd page; neither is
             # read by the prompt, the verifier or the scorer.
             "snippet": p.get("snippet"), "ocr": bool(p.get("ocr"))}
            for number, p in enumerate(passages, start=1)]


# What the cache stores: everything needed to replay an answer, and nothing about this
# particular request (route, timing, seconds) that a future call would compute itself.
_CACHE_FIELDS = ("answer", "status", "gate", "citations", "problems", "attempts",
                 "passages", "model", "prompt_version", "timing")


def _remember(record: dict, question: str, path: pathlib.Path, versions: dict,
              index: dict) -> None:
    """Store an answer, so a later identical question is served instead of re-asked.

    `index` is the page index the answer was built from: the cache keys on its signature
    and stores a hash of each cited page's text, so an answer cannot outlive either the
    corpus on disk or the text it quoted.
    """
    cache.put(question, {key: record[key] for key in _CACHE_FIELDS},
              path=path, index=index, **versions)


def _record(question: str, **fields) -> dict:
    """One answer record, with the fields every path must fill in."""
    base = {"question": question, "answer": "", "status": "unverified", "gate": {},
            "citations": [], "problems": [], "attempts": 0, "passages": [],
            "model": MODEL, "prompt_version": prompt.PROMPT_VERSION, "timing": {},
            "timings": {},
            "seconds": 0.0, "cached": False, "route": {}, "search_question": question,
            "condensed": False}
    base.update(fields)
    return base


def answer(question: str, *, k: int | None = None, model: str = MODEL,
           index: dict | None = None, temperature: float = TEMPERATURE,
           history: list[dict] | None = None, use_cache: bool = True,
           cache_path: pathlib.Path | None = None,
           on_token: Callable[[str], None] | None = None) -> dict:
    """Route, retrieve, ask, verify, retry once, and cache what came back.

    `history` is the chat so far (oldest first). It only matters for a follow-up: it is
    what lets "and in 1990?" be rewritten into a question worth searching for, and what
    the router reads to know a pronoun has a referent at all.

    `on_token` hands each piece of the answer to a caller as the model writes it (Step 7's
    stream). It changes no request and no decision, so a streamed answer is the streamed
    form of the answer the eval scores. `timings` is the same kind of addition: one
    `perf_counter()` per stage, measurement only (D-062).
    """
    started = time.perf_counter()
    marks: dict[str, float] = {}

    def stage(since: float) -> float:
        return round((time.perf_counter() - since) * 1000, 1)

    def done(fields: dict) -> dict:
        marks["total"] = stage(started)
        return _record(question, timings=dict(marks), **fields)

    source = index if index is not None else globals()["index"]()
    mark = time.perf_counter()
    routed = router.route(question, history)
    marks["route"] = stage(mark)

    if routed["route"] == "greeting":
        return done({"answer": GREETING_REPLY, "status": "greeting", "route": routed,
                     "seconds": round(time.perf_counter() - started, 2)})

    # Task 5: rewrite only a follow-up, and only when there is something to rewrite it
    # against. A rewrite that fails leaves the question exactly as it was.
    search_question, condensed = question, False
    marks["condense"] = 0.0
    if routed["condense"]:
        mark = time.perf_counter()
        search_question, condensed = condense.condense(
            question, history, ask=lambda messages: _ask(messages, model, temperature)[0])
        marks["condense"] = stage(mark)

    # The key follows the question that was actually searched: a follow-up condensed
    # against a different history is a different question, and its answer must not be
    # replayed for this one.
    versions = None
    path = cache_path or cache.CACHE_PATH
    marks["cache_lookup"] = 0.0
    if use_cache:
        versions = {"model_version": cache.model_version(model, model_digest(model)),
                    "prompt_version": prompt.PROMPT_VERSION}
        mark = time.perf_counter()
        hit = cache.get(search_question, path=path, index=source, **versions)
        marks["cache_lookup"] = stage(mark)
        if hit is not None:
            return done({**hit, "cached": True, "route": routed,
                         "search_question": search_question, "condensed": condensed,
                         "seconds": round(time.perf_counter() - started, 2)})

    mark = time.perf_counter()
    passages = search_pages(source, search_question, k=k or routed["k"])
    marks["retrieval"] = stage(mark)

    # Task 3's floor: a question nothing scores against is refused without spending a
    # model call, and without giving the model a chance to answer from nothing.
    mark = time.perf_counter()
    checked = gate.pre_ask(passages)
    marks["gate"] = stage(mark)
    if checked["refused"]:
        record = done({"answer": prompt.NOT_FOUND_TEXT, "status": "not_found",
                       "gate": checked, "route": routed,
                       "search_question": search_question, "condensed": condensed,
                       "passages": _passages(passages), "model": model,
                       "seconds": round(time.perf_counter() - started, 2)})
        if use_cache:
            _remember(record, search_question, path, versions, source)
        return record

    mark = time.perf_counter()
    messages = [{"role": "system",
                 "content": prompt.build_system(passages, mode=routed["prompt_mode"])},
                {"role": "user", "content": search_question}]
    marks["prompt_build"] = stage(mark)

    mark = time.perf_counter()
    text, timing = _ask(messages, model, temperature, on_token)
    marks["model_wait"] = stage(mark)
    mark = time.perf_counter()
    verdict = verify.verify_answer(text, passages)
    marks["verify"] = stage(mark)
    attempts = 1

    # D-010: a failed answer is retried once. A refusal is not a failure — the model
    # read the passages and said they do not contain the answer.
    if not verdict["ok"] and not verdict["said_not_found"] and verdict["problems"]:
        messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": prompt.retry_message(verdict["problems"])},
        ]
        mark = time.perf_counter()
        text, timing = _ask(messages, model, temperature, on_token)
        marks["model_wait"] = round(marks["model_wait"] + stage(mark), 1)
        mark = time.perf_counter()
        verdict = verify.verify_answer(text, passages)
        marks["verify"] = round(marks["verify"] + stage(mark), 1)
        attempts = 2

    # The model decides; the gate only records what that decision was and why.
    decision = gate.resolve(verdict)
    status = {"not_found": "not_found", "answer": "verified"}.get(decision["decision"],
                                                                  "unverified")

    record = done({"answer": text, "status": status, "gate": {**checked, **decision},
                   "citations": verdict["citations"], "problems": verdict["problems"],
                   "attempts": attempts, "route": routed,
                   "search_question": search_question, "condensed": condensed,
                   "passages": _passages(passages), "model": model, "timing": timing,
                   "seconds": round(time.perf_counter() - started, 2)})

    # An unverified answer is not cached: it is the one outcome that should be retried
    # rather than replayed.
    if use_cache and status != "unverified":
        _remember(record, search_question, path, versions, source)
    return record


def _parser() -> argparse.ArgumentParser:
    """The CLI, built here so its defaults can be checked without running a model."""
    parser = argparse.ArgumentParser(prog="generation.answer", description=__doc__)
    parser.add_argument("question")
    # None means "use the route's own k": summary and table ask for more context than a
    # normal question, and a default here would silently override every route.
    parser.add_argument("--k", type=int, default=None,
                        help="passages in context (4-6); default: the route's own k")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--json", action="store_true", help="print the whole record")
    parser.add_argument("--history", default="",
                        help="previous question, so a follow-up can be tested")
    parser.add_argument("--no-cache", action="store_true", help="ignore the answer cache")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    history = ([{"role": "user", "content": args.history}] if args.history else None)
    record = answer(args.question, k=args.k, model=args.model, history=history,
                    use_cache=not args.no_cache)
    if args.json:
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] != "unverified" else 1

    route_info = record.get("route") or {}
    print(f"Q: {record['question']}")
    print(f"model {record['model']} | {record['seconds']} s | attempts {record['attempts']} "
          f"| prompt {record['prompt_version']} | route {route_info.get('route')}"
          + (" | cached" if record.get("cached") else ""))
    if record.get("condensed"):
        print(f"searched as: {record['search_question']}")
    print()
    print(record["answer"] or "(empty answer)")
    print()
    print(f"status: {record['status']}")
    gate_info = record.get("gate") or {}
    called = "model asked" if record["attempts"] else "model not asked"
    print(f"gate:   {gate_info.get('decision')} - {gate_info.get('reason')} "
          f"(top {gate_info.get('top')}, floor {gate_info.get('floor')}, {called})")
    for problem in record["problems"]:
        print(f"  - {problem}")
    if record["citations"]:
        print("citations:")
        for citation in record["citations"]:
            print(f"  [{citation['n']}] {citation['file']}, p. {citation['page']}")
    return 0 if record["status"] != "unverified" else 1


if __name__ == "__main__":
    sys.exit(main())
