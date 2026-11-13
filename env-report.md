# Environment report (Step 0)

Target machine: Windows 11 laptop, RTX 3050 Laptop 4GB, 16GB RAM.
Project drive: `C:` (the task said `D:\rag-project`, but this machine has no `D:` volume; the owner confirmed `C:` on 2026-11-13).

## The one re-runnable command

From the project root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\env-report.ps1
```

## Its real output (2026-11-13 10:14:26 +05:45)

```
Reported at : 2026-11-13 10:14:26 +05:45
OS          : Microsoft Windows 11 Pro (build 26300)
CPU         : AMD Ryzen 7 6800HS with Radeon Graphics (8 cores / 16 threads)
RAM         : 15.3 GB

Disk (fixed drives):
  C: free 814.2 GB of 952.8 GB

GPU (nvidia-smi):
NVIDIA GeForce RTX 3050 Laptop GPU, 566.07, 4096 MiB, 377 MiB, 8.6
CUDA (driver-reported):
| NVIDIA-SMI 566.07                 Driver Version: 566.07         CUDA Version: 12.7     |

python      : Python 3.14.10
pip         : 26.2.2
git         : git version 2.56.0.windows.2
LibreOffice : 26.8.2.2
```

The GPU line is `name, driver, total VRAM, VRAM in use (idle), compute capability`.

## Facts

| Item | Value | Note |
|---|---|---|
| Windows | 11 Pro, build 26300 | |
| CPU | AMD Ryzen 7 6800HS, 8C/16T | |
| RAM | 15.3 GB | reported 16 GB class |
| GPU | NVIDIA RTX 3050 Laptop, 4096 MiB, compute 8.6 (Ampere) | |
| NVIDIA driver | 566.07 | |
| CUDA (driver) | 12.7 | runtime the driver supports, not an installed toolkit |
| CUDA toolkit | **not installed** (no `nvcc`, no toolkit folder) | why a prebuilt llama.cpp is used |
| Python | 3.14.10 | `venv` OK, pip 26.2.2 |
| Git | 2.56.0.windows.2 | |
| LibreOffice | 26.8.2.2 | already installed, nothing downloaded |
| Free disk | 814.2 GB on C: | requirement is 50 GB |
| VRAM free at idle | 3719 MiB (4096 − 377) | the display owns the rest |

## Sub-tests run

**LibreOffice headless .docx to PDF (D-019).** A minimal `sample.docx` (1003 bytes, built with the Python standard library, no download) was converted with

```
"C:\Program Files\LibreOffice\program\soffice.exe" --headless --norestore ^
  -env:UserInstallation=file:///C:/Users/sagar/AppData/Local/Temp/lo-step0-profile ^
  --convert-to pdf --outdir artifacts/step0 artifacts/step0/sample.docx
```

Output: `convert ... as a Writer document -> ...\sample.pdf using filter : writer_pdf_Export`.
The PDF is 23240 bytes, header `%PDF-1.7`, 1 page.

> **Finding for Step 3 (D-030):** LibreOffice names the output after the stem (`sample.pdf`), not after the full original name. D-030 requires `<original name>.pdf` (`report.docx` -> `report.docx.pdf`), so the ingestion code must rename after conversion. This test renamed `sample.pdf` to `sample.docx.pdf`.

**NTFS hardlinks from `data/raw/` to `data/corpus/` (D-030).** Created with PowerShell `New-Item -ItemType HardLink`:

```
inode 7036874419057544 links=2 size=20 data/raw/hardlink-test.txt
inode 7036874419057544 links=2 size=20 data/corpus/hardlink-test.txt
```

Same inode and link count 2; writing through the corpus path was visible through the raw path; `fsutil hardlink list` showed both paths; deleting the corpus link left the original intact with `links=1`. **Hardlinks work** — no copying and no extra disk is needed for native PDFs. Test files were deleted afterwards.

Note: `cmd /c mklink /H` failed from Git Bash with "The filename, directory name, or volume label syntax is incorrect" (argument mangling); the PowerShell `New-Item` form works and is what the ingestion step should use.

**Git.** Repository created before Step 0 (D-032). Root commit `initial docs`; `.gitignore` excludes `data/`, `models/`, `*.sqlite`, `*.lance/`, `.venv/`, `__pycache__/` and the `.freebuff/` marker.

## Still to measure (blocked at the download gate)

- llama.cpp CUDA build, GPU offload, prompt and generation speed, VRAM under load.
- Offline proof run with the network disabled.
- Python install itself.

Nothing in this section is measured yet; no number is recorded for it anywhere.
