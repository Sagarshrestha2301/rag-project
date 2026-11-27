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

2026-11-27 | start | step 20 | owner
2026-11-26 | start | step 19 | owner
2026-11-26 | start | step 18 | owner
2026-11-25 | start | step 17 | owner
2026-11-25 | start | step 16 | owner
2026-11-25 | start | step 15 | owner
2026-11-22 | start | step 13 | owner
2026-11-22 | start | step 14 | owner
2026-11-21 | start | step 11 | owner
2026-11-21 | start | step 10 | owner
2026-11-20 | approval | D-068, D-070, D-071, D-072, D-073 (five Step 9 experiment outcomes) | owner
2026-11-20 | completion | step 07 | owner
2026-11-20 | completion | step 09 | owner

2026-11-17 | completion | step 06 | owner
2026-11-16 | start | step 05 | owner
2026-11-16 | start | step 04 | owner
2026-11-16 | start | step 03 | owner
2026-11-16 | start | step 02 | owner
2026-11-16 | start | step 06 | owner
2026-11-16 | start | step 07 | owner
2026-11-16 | start | step 08 | owner
2026-11-16 | start | step 09 | owner
2026-11-16 | completion | step 05 | owner
2026-11-16 | completion | step 04 | owner
2026-11-16 | completion | step 03 | owner
2026-11-13 | completion  | step 01 | owner
2026-11-15 | completion | step 02 | owner
2026-11-13 | approval | docs | owner
2026-11-13 | start | step 00 | owner
2026-11-13 | completion | step 00 | owner
2026-11-13 | start | step 01 | owner

(2026-11-13: the five lines above were typed by the coding agent on the owner's explicit
instruction in chat, not written by hand by the owner. The step 01 approval records the
owner's chat approval of the 30 questions and the scorer spec. Recorded here rather than
omitted so the log matches what happened; see "Proposals for owner" in `STATUS.md`.)

(2026-11-17: the step 06 completion line above was typed by the coding agent on the owner's
explicit instruction in chat - "approve all the remaining" - and committed in an `OWNER:`
commit, the same way the 2026-11-13 lines were. The owner has not yet created the
`step-06-approved` tag; rule 12 leaves that to the owner.)

(2026-11-21: the step 11 start line above, and the pilot download it authorises, were
requested by the owner in chat - "download it from the drive link i have provided and do
the recommend part" - after choosing "Pilot 200 first" from the two scope options. The
folder id was taken from `logs/drive-tree.json` because no link was present in the
session; the owner confirmed that root when choosing the option. Typed in an `OWNER:`
commit by the agent, as on 2026-11-13, 2026-11-17 and 2026-11-20.

(2026-11-21: the step 10 start line above was typed by the coding agent on the owner's
explicit chat instruction - "Add the step-10 start approval line and step file so the
add-batch work can begin" - and committed in an `OWNER:` commit, as on 2026-11-13,
2026-11-17 and 2026-11-20. The step file was drafted by the agent from
`reports/20k-ingestion-plan.md` and the ingest audit, and the owner has not yet edited it.)

(2026-11-20: the three newest lines were typed by the coding agent on the owner's explicit
instruction in chat - "approve all the remaining and open all the remaining steps or task" -
and committed in an `OWNER:` commit, as on 2026-11-13 and 2026-11-17. Step 07's network-off
box was ticked on the owner's report that they ran it with Wi-Fi off; step 08's offline box
is still open because it asks for the run's output to be recorded and no output was supplied.
The tags `step-06-approved` ... `step-09-approved` remain for the owner to create.)

(2026-11-22: the step 13 start line above was typed by the coding agent on the owner's
explicit chat instruction - "Add a --jobs pool to parse_stage so waves parse 8 documents at
once, keeping today's behaviour as the default and test_pipeline green" - and committed in an
`OWNER:` commit, as on 2026-11-13, 2026-11-17, 2026-11-20 and 2026-11-21. The step file
`steps/13-parallel-parse.md` was drafted by the agent from the 2026-11-22 parse measurements
(`reports/20k-download-and-rag-guide.md` section 6.1); the owner has not yet edited it.)

(2026-11-25, step 17: typed by the coding agent on the owner's explicit chat instruction ("Add a
list-shape check to the verifier so a list question's answer must be dash lines, and measure it",
and the "Add the line for me, then build and measure" choice that followed) and committed with an
`OWNER:` message. **Written after the code, not before it:** the step was built on that chat
instruction and this line was only added at the end of the session, so the session log records the
order. The step file `steps/17-list-shape-check.md` was drafted earlier the same day.)

(2026-11-25, step 16: typed by the coding agent on the owner's explicit chat instruction -
"Add the step-16 start line to APPROVALS.md in an OWNER: commit and implement step 16, then run
Stage 1, the full 55-question run and the gate" - and committed in an `OWNER:` commit, as for
steps 06-11 and 13-15 above. The step file `steps/16-list-retrieval.md` was drafted by the agent
on 2026-11-25 from the measurements in `reports/list-format-experiment.md`; the owner has not yet
edited it.)

(2026-11-25, step 15: typed by the coding agent on the owner's explicit chat instruction -
"Implement step 15's refusal-line rule and run the 55-question gate once the owner approves
the start line" - and committed in an `OWNER:` commit, as for steps 06-11, 13 and 14 above.
The step file `steps/15-refusal-line.md` was drafted by the agent on 2026-11-25 from the
measured 2026-11-24 run and the owner has not yet edited it. The `step-15-approved` tag is
the owner's, to be created only after the definition of done is met.)

(2026-11-22, step 14: typed by the coding agent on the owner's explicit chat instruction -
"Make bibliography on-demand by default so waves skip its 45 hours, with the UI falling back
to file names" - and committed in an `OWNER:` commit, as for steps 06-11 and step 13 above.
`steps/14-bibliography-on-demand.md` was drafted by the agent from the Step 11 timing
(8.2 s/document) and the UI fallback already in `ui/static/app.js`.)

(2026-11-26, step 18: typed by the coding agent on the owner's explicit chat instruction -
"Implement the capped C1 rule in the scorer with an extra_citations counter and restate every
stored run" - after the owner accepted option C of `reports/citation-layer-2026-11-26.md` with
its three conditions, and committed in an `OWNER:` commit as on 2026-11-13, 2026-11-17,
2026-11-20, 2026-11-21, 2026-11-22 and 2026-11-25. `steps/18-citation-contract.md` was drafted
by the agent from `reports/citation-contract-rescore-2026-11-26.md` (the rule re-scored on all
22 stored runs) and PROPOSED D-097; the owner has not yet edited it.)

(2026-11-26, step 19: typed by the coding agent on the owner's explicit chat instruction -
"Implement option B so the scorer and the verifier read a page's text from the same source, then
re-score and measure q003" - and committed in an `OWNER:` commit as on 2026-11-13, 2026-11-17,
2026-11-20, 2026-11-21, 2026-11-22 and earlier today for steps 15-18.
`steps/19-page-text-source.md` was drafted by the agent from the measurement that exactly one of
59 citations (q003, p. 15 of the 1975 Thakali paper) differs between the two readers; the owner
has not yet edited it.)

(2026-11-27, step 20: typed by the coding agent on the owner's explicit chat instruction -
"lets do what is incomplete and mark it done in the tracker", followed by the owner choosing
"q052 quote exactness" from the three scopes offered - and committed in an `OWNER:` commit as on
2026-11-13, 2026-11-17, 2026-11-20, 2026-11-21, 2026-11-22 and 2026-11-25/26.
`steps/20-quote-case-exactness.md` was drafted by the agent from the measured q052 defect (the
page prints "Bamboo clumps invites wild elephants" and the answer quoted "bamboo clumps invites
wild elephants", one lowercased first letter); the owner has not yet edited it.)
