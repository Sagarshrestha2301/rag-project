"""Re-run the implemented verifier over the 55 saved answers and report status changes.

The saved answers are the final text after the one allowed retry, so a flip here means
"this answer would now be retried, and would be unverified if the retry failed too".
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from generation import verify

RUN = pathlib.Path("eval/runs/2026-11-16-step6-full/run.jsonl")


def main() -> int:
    rows = [json.loads(line) for line in RUN.read_text(encoding="utf-8").splitlines() if line.strip()]
    flips, gained, counts = [], [], {"verified": 0, "not_found": 0, "unverified": 0}
    for row in rows:
        passages = [{"doc": item.get("file"), "page": item["page"]}
                    for item in row.get("retrieved") or []]
        result = verify.verify_answer(row.get("answer") or "", passages)
        now = ("not_found" if result["said_not_found"]
               else "verified" if result["ok"] else "unverified")
        before = row.get("status")
        counts[before] = counts.get(before, 0) + 1
        if before != now:
            entry = {"id": row["id"], "before": before, "now": now,
                     "problems": result["problems"]}
            (gained if now == "verified" else flips).append(entry)

    print("saved statuses:", counts)
    print(f"verified -> not accepted now: {len(flips)}")
    print(f"not accepted -> verified now: {len(gained)}")
    for entry in flips:
        print(f"\n  {entry['id']}: {entry['before']} -> {entry['now']}")
        for problem in entry["problems"][:4]:
            print(f"     {problem[:150]}")
    for entry in gained:
        print(f"\n  {entry['id']}: {entry['before']} -> verified (was: "
              f"{(entry['problems'] or ['no problems recorded'])[0][:100]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
