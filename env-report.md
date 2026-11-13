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

## llama.cpp on the GPU

**Build:** `b12340`, prebuilt Windows CUDA 12.4 zip plus the matching `cudart` zip, unpacked to `tools\llama.cpp\`. Chosen over a local build because no CUDA toolkit and no MSVC are installed (a local build would need the ~3 GB toolkit plus Build Tools), and over `winget`, which installs system-wide rather than into the project.

Why not the newest tag: `b12352` and `b12300` publish **source archives only** (0 binaries). `b12340` is the newest tag with Windows CUDA assets.

**Run:** `llama-server.exe --model models\qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 --ctx-size 4096 --n-gpu-layers 99 --threads 8`

**Offload evidence** (`artifacts/step0/llama-offload-evidence.txt`, from a `-lv 5` run):

```
common_param:   - CUDA0   : NVIDIA GeForce RTX 3050 Laptop GPU (4095 MiB, 3303 MiB free)
llama_prepare_model_devices: using device CUDA0 (NVIDIA GeForce RTX 3050 Laptop GPU) (0000:01:00.0) - 3303 MiB free
load_tensors: offloaded 29/29 layers to GPU
load_tensors: layer   0..28 assigned to device CUDA0
```

| Measurement | Value |
|---|---|
| Layers offloaded | **29 / 29** (all), layer indices 0-28 all on `CUDA0` |
| Prompt processing | 22 tokens in 100 ms -> **219.0 tok/s** |
| Generation | 96 tokens in 1453 ms -> **65.4 tok/s** |
| VRAM with model resident | **1622 MiB** of 4096 (2343 MiB free) |
| VRAM idle (before load) | 377 MiB (desktop) |
| Context / threads | 4096 tokens, 8 threads, 4 slots |

**Test output** (`artifacts/step0/completion.json`), temperature 0:

> Hybrid retrieval combining BM25 and dense vectors works better than dense vectors alone because dense vectors capture the semantic meaning of words, while BM25 captures the frequency of words. By combining the two, the model can better understand the context and meaning of the text, leading to more

## Offline proof (network blocked)

`scripts/offline-proof.ps1` blocks `llama-server.exe` inbound and outbound at Windows Firewall, starts the server, runs a prompt, and always removes the rule afterwards. The whole machine's network was **not** switched off, because that would also drop the remote coding session; the process itself was cut off instead.

```
firewall rules active during test: 2 (2 = inbound + outbound block)
server pid: 27680
health ready with network blocked: True
completion returned: 26 tokens at 74.2 tok/s
answer:  The capital of Nepal is Kathmandu, and it sits on the two rivers, the Ganges and the Karnali.
vram used during run: 1594 MiB
firewall rules removed (remaining: 0)
offline run: PASS
```

The answer is factually wrong (Kathmandu sits on the Bagmati and Bishnumati) — expected for a 1.5B model used only as a plumbing test, and a reminder that citations and the eval set are what will make answers trustworthy.

## Downloaded files (SHA-256 checked against the publisher)

| Name | Source | Version | SHA-256 | Path |
|---|---|---|---|---|
| `llama-b12340-bin-win-cuda-12.4-x64.zip` | github.com/ggml-org/llama.cpp releases | b12340 | `72c3654c1495c7b08444ac8edf5e1c658943e9721a70787074612e3480286f9e` | `tools/llama.cpp/` |
| `cudart-llama-bin-win-cuda-12.4-x64.zip` | same release | b12340 | `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6` | `tools/llama.cpp/` |
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | main | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` | `models/` |

All three local hashes match the digest published by GitHub and Hugging Face. Sizes were checked against `Content-Length` before extraction.

## Python dependency check (no wheel installed)

Direct dependencies, checked from PyPI wheel filenames on 2026-11-13:

| Package | Version | Windows wheel | 3.12 | 3.14 |
|---|---|---|---|---|
| pymupdf4llm | 2.1 | `py3-none-any` | yes | yes |
| pymupdf | 2.1 | `cp311-abi3` | yes | yes |
| pdfplumber | 0.11.10 | `py3-none-any` | yes | yes |
| lancedb | 0.41.0 | `cp310-abi3` | yes | yes |
| sentence-transformers | 6.3.0 | `py3-none-any` | yes | yes |
| torch | 2.15.0 | `cp314` | yes | yes |
| fastapi | 0.162.5 | `py3-none-any` | yes | yes |
| uvicorn | 0.54.0 | `py3-none-any` | yes | yes |
| httpx | 0.28.1 | `py3-none-any` | yes | yes |

All nine direct dependencies can install on both interpreters. Transitive dependencies were not checked, and nothing was installed: the owner is holding the Python item until the interpreter is chosen. See the proposal in `STATUS.md`.

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

**Git.** Repository created before Step 0 (D-032). Root commit `initial docs`; `.gitignore` excludes `data/`, `models/`, `tools/`, `*.sqlite`, `*.lance/`, `.venv/`, `__pycache__/` and the `.freebuff/` marker.

## Not measured

- Parse speed and embedding speed (Steps 3 and 4).
- Any model larger than 1.5B: VRAM headroom for a 3-4B Q4 model is not established, only that 1.62 GB of 4 GB is used by a 1.5B model at 4k context.
