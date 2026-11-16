# Owner kit

Prepared by the coding agent on 2026-11-15. **Nothing in this folder has been run.**
No approval line was added to `APPROVALS.md`, no tag was created, and no entry in
`DECISIONS.md` was approved — only you may do those, from a commit whose message
starts with `OWNER:`.

On 2026-11-16 the owner approved all 20 pending decisions in chat (D-058 and D-059 were proposed and approved the same day, for Step 6), so the script's
`$Decisions` table is pre-filled: `APPROVE` for seventeen and `SUPERSEDE by D-047` for
D-046, which a later entry replaced. The verdicts are filled in so you review the
wording you are signing, not so you retype eighteen values; overwrite any of them.

Three files:

| File | What it is | Safe to run? |
|---|---|---|
| `apply-owner-actions.ps1` | Writes the missing approval lines, creates the missing tags, and records a verdict for all 20 pending decisions. | Read it first; it refuses to act until every decision in its table has a verdict. |
| `step-file-edits.patch` | A unified diff for two wording fixes in `steps/02` and `steps/03`. **Not applied.** | `git apply --check` passes; you apply it when you want it. |
| `OWNER-CHECKLIST.md` | What only you can decide, and what only you can do by hand. | Read it. |

## Why this kit exists

`APPROVALS.md` has completion lines for steps 01 and 02, but **no start line for step 02** (its completion is there, its start is not), none for steps 03 and 04, and none for step 05. `git tag` lists nothing at all. Steps 2, 3, 4 and 5 were worked on anyway, on explicit chat instruction (recorded in `STATUS.md`), which left the record behind reality. This kit closes that gap in one reviewable run instead of asking you to remember a sequence of commands.

## Before you run the script

1. Commit your own `APPROVALS.md` edit, so the tree is clean. The script stops if it is not:
   `git add APPROVALS.md` then `git commit -m "OWNER: record step 01 and step 02 completion"`.
   Check the diff first: if you replaced the `approval | step 01` line rather than adding a completion line under it, the log no longer records that step 01 was approved.
2. Open `apply-owner-actions.ps1` and check the `$Decisions` table near the top: all 21 entries have a verdict filled in already, each with the sentence that will be written to `DECISIONS.md`. Change any you disagree with to `'REJECT'` or back to `'PENDING'`. The script refuses to run while any entry is `'PENDING'`, and the verdicts are yours to overwrite — the table is filled in so you review the wording, not so you retype twenty-one values.
3. Read `OWNER-CHECKLIST.md` for the two judgement calls inside the script (the tags and `$AcceptStep2`).

## Dry run, then real run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1 -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1
```

`-WhatIf` prints every action and changes nothing: it creates no lines, no tags and
no commits. The real run does four things in order, each with its own `OWNER:` commit
where a commit is needed:

1. **APPROVALS.md** — adds `completion` lines for steps 01, 02, 04 and 05 and `start` lines for steps **02, 03, 04, 05 and 06**, dated the day you run it. The step 06 start line is what opens Step 6 and is gated by `$StartStep6`; it creates no tag, because a step is tagged only when its definition of done is finished. A line whose step and action already exist is skipped, so running it twice does not duplicate anything.
2. **Tags** — creates `step-00-approved` and `step-01-approved`, plus `step-02-approved`, `step-04-approved` and `step-05-approved` for the switches you leave at `$true` (`$AcceptStep2`, `$AcceptStep4`, `$AcceptStep5`).
3. **DECISIONS.md** — writes one line per decision in the table: `APPROVED <id> by the owner <date>` for each approval, and `SUPERSEDED D-046 by D-047` for the one decision that a later entry replaced. Each line goes directly *above* the entry it answers, so the entry keeps its indented body. A decision that already has a verdict line of any kind is skipped, so a second run cannot add a contradicting one.
4. **Check** — prints the two `APPROVALS.md` checks A and B from that file, so you can see the result immediately.

## The one thing the script cannot fix

The tags point at the commit that is `HEAD` when you run it. There is no historical
completion commit for step 00 or step 01 to tag — those completions were recorded in
`APPROVALS.md` (uncommitted, until you commit it) and never in a commit of their own.
The script prints this warning rather than pretending the tag marks the original
completion commit.
