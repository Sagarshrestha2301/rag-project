# Rules for every coding agent

You may be a free model with a small context window and no memory of earlier sessions. These rules make the project safe to hand between agents.

## Start of every session
1. Read this file, then `STATUS.md`, then the current `steps/NN-*.md`. Read other docs only if needed.
2. Run `git status`. If the working tree is not clean, stop and tell the owner (rule 14).
3. Open `APPROVALS.md` and confirm the step you were asked to work on has a start approval by the owner. Approvals exist only there and in the owner's `step-NN-approved` tags; a cell in `STATUS.md` is not an approval. If there is no approval: do nothing except answer questions.

## How you are given a task
Every task has three parts: TASK, CONTEXT, OUTPUT. If a part is missing or unclear, ask before starting.
- **TASK:** the step and one sub-task, in one sentence.
- **CONTEXT:** the only files you may rely on. The step file lists them under "Context to read". Do not rely on memory; use the versions pinned in `STATUS.md`.
- **OUTPUT:** the files to create or change, a worked example of the expected result, the commit message, and the handoff format below.

Template the owner pastes:
```
TASK: Step NN, sub-task: <one sentence>
CONTEXT: AGENTS.md, STATUS.md, steps/NN-*.md, <other files>
OUTPUT: <files>; example: <input -> expected output>; commit: "step NN: ..."
```

## Hard rules
1. **One step at a time.** Never start a step that is not approved by the owner. Never work ahead.
2. **No installs, downloads, or code** unless the current approved step says so. List what you will install and why, and wait if the step does not already list it.
3. **Regression gate** (exact rule in `EVAL.md`): a retrieval or prompt change is accepted only if there is no unexplained pass-to-fail question and no metric drops by more than one question, measured against both the last accepted baseline and the baseline from the start of the step. Not-found accuracy (a) must not drop at all. Run the eval before and after. Never edit the eval set or the gold answers to make a score pass. Faithfulness from a local LLM judge is a secondary signal only, never a gate.
4. **Never invent facts, numbers, file names or results.** If you did not measure it, write "not measured".
5. **Never modify the owner's original documents or the corpus.** `data/raw/` (originals) and `data/corpus/` (the PDFs the system uses, see rule 11) are read-only.
6. **Everything offline at runtime.** No network calls in application code. Bind servers to localhost only. Enforcement:
   - After the approved one-time downloads, every launch script and config sets offline mode (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`) and points parsers and embedders at local model folders under `models/`. Set it in the scripts, not only in your own shell.
   - Libraries often download models on first use. When a step introduces a library, check what it downloads and when, and download it deliberately during the approved download window (this is not yet verified for our pinned versions).
   - Keep a list of every downloaded file (name, source, version, SHA-256, path) in `STATUS.md`.
   - Offline proof: at the end of Steps 0, 5, 6 and 8, run the step's eval or test once with the network disabled (Wi-Fi/Ethernet off) and record "offline run: pass" with the output. Step 7 already requires this.
7. **Pin versions** of every dependency, model file and tool (including the LibreOffice version); record them in `STATUS.md`.
8. **Determinism for evals:** temperature 0, fixed seeds, same model files.
9. **Do not change decisions** in `DECISIONS.md`. Propose a change, explain why, wait for approval.
10. **Keep VRAM free for the LLM.** Embeddings and reranker on CPU unless a benchmark approved by the owner says otherwise.
11. **Converted PDFs are the corpus.** `data/corpus/` holds exactly the PDFs the system reads, in the same relative folders as `data/raw/`. Native PDFs are hardlinked from `data/raw/` (copied only if the Step 0 test shows hardlinks do not work), so they take no extra disk space. Word files are converted once with the pinned LibreOffice version and stored as the full original file name plus `.pdf` (`report.docx` becomes `report.docx.pdf`). All gold pages, citations and UI page links refer to files in `data/corpus/` (SHA-256 recorded for every file). Never convert again silently. Changing the converter or its version needs owner approval and a re-check of every gold page.
12. **Version control.** The project is a git repository, created by the owner before Step 0 (D-032).
    - Commit after each verified sub-task. Message format: `step NN: what changed (verified: how)`. Stage files by name; never use `git add -A` or `git commit -a`.
    - Only the owner creates the tag `step-NN-approved` and writes in `APPROVALS.md`. Never create, move or delete a `step-*` tag.
    - Never rewrite history: no `reset --hard`, `rebase`, `commit --amend` of earlier commits, `push --force`, or `filter-branch`. To undo, use `git revert`.
    - Do not commit data, models, indexes or `.venv` (see `.gitignore`).
13. **Protected files (owner-only edits).** You must not edit:
    - `AGENTS.md`, `PLAN.md`, `REQUIREMENTS.md`, `APPROVALS.md`
    - `EVAL.md` except appending rows to the Results table
    - `eval/questions.jsonl` existing questions, gold answers and splits (new dev questions only through the process in `EVAL.md`)
    - `DECISIONS.md` existing entries (you may append entries marked "PROPOSED by agent, pending owner")
    - The text of the tasks and definition of done in `steps/NN-*.md` (you may tick a checkbox only after you verified it and put the evidence in `STATUS.md`)

    If you think a protected file is wrong, write it under "Proposals for owner" in `STATUS.md` and stop. Owner edits are committed with a message starting `OWNER:`. Before every commit, check `git diff --cached --name-only` (the staged files): if it lists a protected file and the message does not start with `OWNER:`, do not commit.

14. **Clean working tree.** Start every session with `git status`. If a protected file has uncommitted changes (the owner may be mid-edit), or the tree is otherwise not clean, stop and tell the owner. Do not commit, stash, reset, checkout or overwrite anything. The owner commits their own edits first, with an `OWNER:` message. End every session with a clean tree: commit verified work, or tell the owner what is left uncommitted and why.

## Code rules (when a step involves code)
1. **Inspect before writing.** Search the existing code for similar logic first. Reuse or extend it; never copy-paste a second version (DRY).
2. **Easy to extend.** Parsers, chunkers, embedders, rerankers, intent routes and metrics each sit behind a small common interface and are registered in one place, so adding one does not mean editing the pipeline.
3. **Quality is part of done, not just "it runs":** clear names, small functions, no dead code, errors with clear messages.
4. **Mark unfinished work** as `TODO(step-NN): what needs doing`. Never leave a silent gap. List every new TODO in your handoff.
5. **Show, don't just tell.** Each module has a short usage example (docstring or example file) with real values.
6. **Web UI (Step 7):** BEM class names (`block__element--modifier`), one shared event handler per event type (event delegation), shared helper functions, no duplicated handlers.

## Working style
- Small changes, each verified before the next. Show the command and its real output as evidence.
- Keep files small and single-purpose so a small context window can read them.
- Windows 11: use `pathlib`, UTF-8 everywhere, no hard-coded separators, no bash-only commands in scripts.
- Log with timestamps; long jobs must be resumable.
- **Plan before code when it is not clear.** If there is more than one reasonable way to do a task, or you cannot describe the result clearly, do not start coding. Write a short plan with the options under "Proposals for owner" in `STATUS.md` and wait.
- If blocked or unsure, stop and ask the owner. Do not guess.

## End of every session (mandatory)
Update `STATUS.md`: step state, measured facts, next action, one log line.
Add proposed decisions to `DECISIONS.md` (marked PROPOSED). Append eval results to the `EVAL.md` Results table if the eval was run. Commit.

## Handoff format (last message of the session)
- Done: what changed (files, commit ids).
- Verified: how, with real output.
- Not done / risks.
- Next action and what approval is needed.

## Definition of done for any step
All items in the step's definition of done verified, docs updated, code follows the Code rules, eval results recorded (when the step requires it), completion approval recorded by the owner in `APPROVALS.md` and the step tagged by the owner.
