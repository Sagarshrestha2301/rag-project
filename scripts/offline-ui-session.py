"""Five questions through the running UI server, for the Step 7 offline proof.

Run by `scripts/offline-ui-proof.ps1` while the network is blocked, so a question that
needed the internet could not produce an answer. Two of the five are follow-ups: a
back-reference forces the condensation path, which itself makes a model call.

What is required: every question must end with a `done` event carrying non-empty answer
text and a status the UI knows. Accuracy is not asserted here - that is `eval/`'s job and
it is measured with the cache off; this proves the UI answers with no network.

Usage:
    .venv\\Scripts\\python.exe scripts\\offline-ui-session.py [http://127.0.0.1:8000]

Example of one line of output:
    [3/5] table      done in  9.4 s  answer 21 chars  "…"  follow-up: no
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

DEFAULT_SERVER = "http://127.0.0.1:8000"
STATUSES = {"verified", "not_found", "unverified", "greeting"}

# (question, is follow-up). The follow-ups only mean something after the turn above them.
QUESTIONS = [
    ("What was the 24-hour rainfall depth recorded at Tistung on 20 July 1993?", False),
    ("And what was it at Ghantemadi?", True),
    ("How many households in the Terai believe in bamboo taboos, and what percentage is that?", False),
    ("What about the total number of households surveyed?", True),
    ("Into which two types does Watanabe classify glaciers in the Nepal Himalayas?", False),
]


def ask(server: str, question: str, history: list[dict]) -> dict:
    """POST one turn and fold the event stream into a result.

    A `token` event means the model is writing; `done` carries the payload the UI renders.
    Anything else (an `error` event, a stream that ends without `done`) is a failure.
    """
    body = json.dumps({"messages": history + [{"role": "user", "content": question}]}).encode()
    request = urllib.request.Request(f"{server}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    tokens: list[str] = []
    payload: dict | None = None
    error: str | None = None

    with urllib.request.urlopen(request, timeout=300) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            event = json.loads(line)
            if event["event"] == "token":
                tokens.append(event["text"])
            elif event["event"] == "done":
                payload = event["payload"]
            elif event["event"] == "error":
                error = event["message"]

    return {"question": question, "payload": payload, "error": error,
            "streamed": "".join(tokens), "seconds": round(time.perf_counter() - started, 1)}


def main(argv: list[str]) -> int:
    server = argv[1] if len(argv) > 1 else DEFAULT_SERVER
    history: list[dict] = []
    failures = 0

    for number, (question, followup) in enumerate(QUESTIONS, start=1):
        result = ask(server, question, history)
        payload = result["payload"]
        if result["error"] or payload is None:
            failures += 1
            print(f"[{number}/{len(QUESTIONS)}] FAILED  {result['error'] or 'no done event'}")
            history.append({"role": "user", "content": question})
            continue

        answer = payload.get("answer") or ""
        status = payload.get("status")
        route = (payload.get("route") or {}).get("route")
        ok = bool(answer.strip()) and status in STATUSES
        failures += 0 if ok else 1
        print(f"[{number}/{len(QUESTIONS)}] {status:10} done in {result['seconds']:5.1f} s  "
              f"answer {len(answer):3} chars  route={route}  follow-up: "
              f"{'yes' if followup else 'no'}  cached: {payload.get('cached')}")
        print(f"          {answer.strip()[:110]}")
        if not ok:
            print(f"          FAILED: status={status!r}, empty answer={not answer.strip()}")
        history += [{"role": "user", "content": question},
                    {"role": "assistant", "content": answer}]

    print(f"\nquestions answered: {len(QUESTIONS) - failures}/{len(QUESTIONS)}")
    print("offline ui session: " + ("PASS" if failures == 0 else "FAIL"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
