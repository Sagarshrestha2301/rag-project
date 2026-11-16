# Owner kit

Prepared by the coding agent on 2026-11-15. **Nothing in this folder has been run.**
No approval line was added to `APPROVALS.md`, no tag was created, and no entry in
`DECISIONS.md` was approved — only you may do those, from a commit whose message
starts with `OWNER:`.

Three files:

| File | What it is | Safe to run? |
|---|---|---|
| `apply-owner-actions.ps1` | Writes the missing approval lines, creates the two missing tags, approves five decisions and supersedes a sixth. | Read it first; it refuses to act until you fill in its decision variables. |
| `step-file-edits.patch` | A unified diff for two wording fixes in `steps/02` and `steps/03`. **Not applied.** | `git apply --check` passes; you apply it when you want it. |
| `OWNER-CHECKLIST.md` | What only you can decide, and what only you can do by hand. | Read it. |

## Why this kit exists

`APPROVALS.md` has completion lines for steps 01 and 02, but **no start line for step 02** (its completion is there, its start is not), none for steps 03 and 04, and none for step 05. `git tag` lists nothing at all. Steps 2, 3, 4 and 5 were worked on anyway, on explicit chat instruction (recorded in `STATUS.md`), which left the record behind reality. This kit closes that gap in one reviewable run instead of asking you to remember a sequence of commands.

## Before you run the script

1. Commit your own `APPROVALS.md` edit, so the tree is clean. The script stops if it is not:
   `git add APPROVALS.md` then `git commit -m "OWNER: record step 01 and step 02 completion"`.
   Check the diff first: if you replaced the `approval | step 01` line rather than adding a completion line under it, the log no longer records that step 01 was approved.
2. Open `apply-owner-actions.ps1` and change the six decision variables near the top from `'PENDING'` to `'APPROVE'` (or `'REJECT'`), after reading each decision in `DECISIONS.md`. The script refuses to run while any of them is still `'PENDING'` — that is deliberate, because a decision approved by a script is not an approval.
3. Read `OWNER-CHECKLIST.md` for the two judgement calls inside the script (the tags and `$AcceptStep2`).

## Dry run, then real run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1 -WhatIf
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts\owner-kit\apply-owner-actions.ps1
```

`-WhatIf` prints every action and changes nothing: it creates no lines, no tags and
no commits. The real run does four things in order, each with its own `OWNER:` commit
where a commit is needed:

1. **APPROVALS.md** — adds `completion` lines for steps 01 and 02 and `start` lines for steps **02, 03, 04 and 05**, dated the day you run it. A line whose step and action already exist is skipped, so running it twice does not duplicate anything.
2. **Tags** — creates `step-00-approved` and `step-01-approved` (and `step-02-approved` only if you set `$AcceptStep2 = $true`).
3. **DECISIONS.md** — adds an `APPROVED … by the owner <date>` line after each of D-038, D-040, D-042, D-043 and D-044, and a `SUPERSEDED D-039 by D-040` line after D-039.
4. **Check** — prints the two `APPROVALS.md` checks A and B from that file, so you can see the result immediately.

## The one thing the script cannot fix

The tags point at the commit that is `HEAD` when you run it. There is no historical
completion commit for step 00 or step 01 to tag — those completions were recorded in
`APPROVALS.md` (uncommitted, until you commit it) and never in a commit of their own.
The script prints this warning rather than pretending the tag marks the original
completion commit.
