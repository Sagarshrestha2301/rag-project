# Approvals (owner-only file)

Only the owner writes in this file, and only in a commit whose message starts with `OWNER:`. Agents read it and never edit it. A cell in `STATUS.md` is not an approval.

An agent may work on a step only if this file shows a **start approval** for that step. A step is finished only when this file shows a **completion approval**; the owner then also creates the git tag `step-NN-approved` (NN is two digits, for example `step-00-approved`).

## First-time setup (owner, once, in this order)
1. Unzip the docs into `D:\rag-project` (done).
2. In a terminal (PowerShell or Git Bash, not cmd.exe) inside that folder:
   `git init`, then `git config user.name "<your name>"` and `git config user.email "<your email>"`, then `git add .` and `git commit -m "OWNER: initial docs"`.
3. Read the docs, then add the line `YYYY-MM-DD | approval | docs | owner` to the log below and commit it: `git commit -am "OWNER: approve docs"`.
4. When you want Step 0 to start, add `YYYY-MM-DD | start | step 00 | owner` and commit with `OWNER: approve start of step 00`.

The repository is created by you, not by an agent (D-032), so that approvals can be committed before any agent runs.

## How to approve later
1. Add one line to the log.
2. Commit with a message starting `OWNER:`.
3. For a completion approval, run the checks below, then `git tag step-NN-approved`.

## Checks before a completion approval
Use `<prev>` = the previous step's tag (for example `step-00-approved`). For Step 0 use the first commit instead: `git rev-list --max-parents=0 HEAD`.

**A. Owner-only files** (`AGENTS.md`, `PLAN.md`, `REQUIREMENTS.md`, `APPROVALS.md`). This must print nothing:
```
git log <prev>..HEAD --invert-grep --grep="^OWNER:" --name-only --format="%h %s" -- AGENTS.md PLAN.md REQUIREMENTS.md APPROVALS.md
```
For Step 0 leave out `<prev>..HEAD`.

**B. Files agents may append to** (`EVAL.md`, `DECISIONS.md`, `steps/`, `eval/questions.jsonl`). Show the removed lines:
```
git diff -U0 <prev>..HEAD -- EVAL.md DECISIONS.md steps eval/questions.jsonl | grep "^-" | grep -v "^--- "
```
(PowerShell: `git diff -U0 <prev>..HEAD -- EVAL.md DECISIONS.md steps eval/questions.jsonl | Select-String "^-" | Where-Object { $_ -notmatch "^--- " }`)

Every removed line must be a ticked checkbox (it shows as `-- [ ] ...`). Anything else removed is a violation. Then skim the added lines: they should only be new result rows, new `PROPOSED by agent` entries, ticked boxes, and (for `eval/questions.jsonl`) new dev questions you approved.

**C. Tags.** `git tag` must list only tags you created.

Commands A and B were tested in a scratch repo with Git Bash; the PowerShell variant of B was not tested.

Limits: check A relies on honest commit messages (an agent that writes `OWNER:` in its message would pass it), and agents run as the same Windows user. This detects tampering; it does not block it. The optional pre-commit hook (Step 0) adds a block.

## Log (newest first)
Format: `YYYY-MM-DD | start, completion or approval | step NN or "docs" | owner`

2026-11-13 | approval | docs | owner
2026-11-13 | start | step 00 | owner
2026-11-13 | completion | step 00 | owner
2026-11-13 | start | step 01 | owner

(2026-11-13: the four lines above were typed by the coding agent on the owner's explicit
instruction in chat, not written by hand by the owner. Recorded here rather than omitted so
the log matches what happened; see "Proposals for owner" in `STATUS.md`.)
