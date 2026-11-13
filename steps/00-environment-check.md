# Step 0: Environment check

**Goal:** prove the machine can run the GPU LLM stack, and pin every version.
**Needs approval to start:** yes. This is the first step that installs or downloads anything; list each item and get approval first.

## Tasks
1. Record: Windows build, CPU, RAM, GPU model, NVIDIA driver, CUDA version, Python, Git, free disk on the project drive.
2. Get a CUDA-enabled llama.cpp build (prebuilt release or local build; choose and explain).
3. Run it with one small test model fully on GPU. Record VRAM used, prompt speed and generation speed.
4. Create an isolated Python environment plan and a pinned requirements file (empty of app code).
5. Install LibreOffice (D-019), pin its version, and test one headless Word to PDF conversion on a sample .docx.
6. Confirm the git repository exists (created by the owner, D-032), `.gitignore` is in place and the working tree is clean. Propose, and wait for approval of, an optional pre-commit hook that blocks edits to protected files (D-025); hooks live in `.git/hooks`, so the owner installs it.
7. Create the list of downloaded files (name, source, version, SHA-256, path) in `STATUS.md` and set offline mode in the launch script (D-026).
8. Run the llama.cpp test once more with the network disabled.
9. Test whether NTFS hardlinks work on the project drive (create a hardlink of a test file from `data/raw/` into `data/corpus/`, check both paths show the same content). Record the result; if hardlinks fail, plan copying and re-check the disk budget (D-030).
10. Write `STATUS.md` "Measured facts" and a short `env-report.md`.

## Definition of done
- [ ] llama.cpp server answers a test prompt using the GPU (evidence: log showing offloaded layers + output)
- [ ] VRAM and RAM numbers recorded
- [ ] All tool and model versions pinned in `STATUS.md`, including LibreOffice
- [ ] One .docx converted to PDF headless with the pinned LibreOffice (output file shown)
- [ ] Git repository exists (created by the owner) with `.gitignore` in place; working tree clean
- [ ] Hardlink test result recorded (works / does not work, with output)
- [ ] Downloaded-file list started; offline mode set in the launch script
- [ ] Offline proof: llama.cpp test passes with the network disabled
- [ ] Free disk on the project drive confirmed at 50GB or more (or flagged)
- [ ] No application code written

## Context to read
`AGENTS.md`, `STATUS.md`, this file, `DECISIONS.md` (D-019, D-024, D-026, D-030), `APPROVALS.md`.

## Expected output
`env-report.md` with one re-runnable command and its real output; `STATUS.md` updated (measured facts, pinned versions, downloaded-file list); a launch script that sets offline mode; a pinned requirements file. Format example only (not a measurement): `llama-server: layers offloaded to GPU = <n>/<total>, generation = <x> tok/s, VRAM used = <y> GB`.

## Verification
Owner can re-run the single command in `env-report.md` and see the same result.

## Risks
Driver/CUDA mismatch; not enough free VRAM because Windows uses some for the display (record the real free amount).
