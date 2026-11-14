"""Step 2 comparison row for the chosen model under the recorded runtime (Ollama).

Measures, against the model Ollama actually serves:
  - time to first token (TTFT) for a short prompt and for a realistic 5-chunk
    RAG prompt (~3-4k tokens), which is what the 20 s target is about
  - prompt-processing and generation speed from Ollama's own counters
  - peak VRAM during generation, sampled from nvidia-smi
  - the answer, so the citation format can be eyeballed

Re-run:
    .venv\\Scripts\\python.exe benchmarks\\llm\\measure-ollama.py

Writes `benchmarks/llm/ollama-measure.json` and prints the table row.
No network access beyond 127.0.0.1.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import subprocess
import threading
import time
import urllib.request

import pymupdf

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen2.5"
NUM_CTX = 4096
OUT = pathlib.Path("benchmarks/llm/ollama-measure.json")
CORPUS = pathlib.Path("data/corpus")

SHORT = "In one sentence, what do the authors conclude about extreme rainfall in Nepal?"
LONG = ("Using the excerpts above, summarise how extreme rainfall relates to flooding, "
        "citing the page you took each statement from.")


def five_chunk_prompt() -> str:
    """Five real corpus pages, the shape of the Step 5 prompt."""
    pages = []
    for pdf in sorted(CORPUS.glob("*.pdf"))[:3]:
        with pymupdf.open(pdf) as doc:
            for page in doc[:2]:
                text = " ".join(page.get_text().split())
                if len(text) > 400:
                    pages.append(f"[{pdf.stem[:24]} p{page.number + 1}] {text[:2400]}")
    return "\n\n".join(pages[:5]) + "\n\n" + LONG


class VramSampler(threading.Thread):
    """Poll nvidia-smi while a request runs; keep the peak."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak = 0
        self._halt = threading.Event()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip().splitlines()
                if out:
                    self.peak = max(self.peak, int(out[0]))
            except (OSError, ValueError, subprocess.SubprocessError):
                return
            self._halt.wait(0.25)

    def stop(self) -> int:
        self._halt.set()
        self.join(timeout=2)
        return self.peak


def chat(prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "stream": True,
        "options": {"temperature": 0, "num_ctx": NUM_CTX},
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    sampler = VramSampler()
    sampler.start()
    started = time.perf_counter()
    first = None
    text = ""
    final: dict = {}
    with urllib.request.urlopen(request, timeout=900) as response:
        for line in response:
            if not line.strip():
                continue
            chunk = json.loads(line)
            piece = (chunk.get("message") or {}).get("content", "")
            if piece and first is None:
                first = time.perf_counter() - started
            text += piece
            if chunk.get("done"):
                final = chunk
    peak = sampler.stop()
    total = time.perf_counter() - started

    prompt_n = final.get("prompt_eval_count") or 0
    gen_n = final.get("eval_count") or 0
    prompt_s = (final.get("prompt_eval_duration") or 1) / 1e9
    gen_s = (final.get("eval_duration") or 1) / 1e9
    return {
        "prompt_tokens": prompt_n,
        "generated_tokens": gen_n,
        "ttft_s": round(first, 2) if first else None,
        "total_s": round(total, 2),
        "prompt_tok_s": round(prompt_n / prompt_s, 1) if prompt_n else None,
        "gen_tok_s": round(gen_n / gen_s, 1) if gen_n else None,
        "vram_peak_mib": peak,
        "answer": text.strip()[:400],
    }


def main() -> int:
    results = {"model": MODEL, "num_ctx": NUM_CTX, "runtime": "ollama",
               "short": chat(SHORT), "rag": chat(five_chunk_prompt())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    short, rag = results["short"], results["rag"]
    print(f"model      {MODEL} via Ollama, num_ctx {NUM_CTX}")
    print(f"short      prompt {short['prompt_tokens']:>4} tok  TTFT {short['ttft_s']}s  "
          f"gen {short['gen_tok_s']} tok/s  VRAM {short['vram_peak_mib']} MiB")
    print(f"5-chunk    prompt {rag['prompt_tokens']:>4} tok  TTFT {rag['ttft_s']}s  "
          f"total {rag['total_s']}s  prompt {rag['prompt_tok_s']} tok/s  gen {rag['gen_tok_s']} tok/s  "
          f"VRAM {rag['vram_peak_mib']} MiB")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
