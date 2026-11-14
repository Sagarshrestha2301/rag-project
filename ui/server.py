"""Local chat UI server: retrieval + Ollama, localhost only, offline.

Every answer is built from pages of `data/corpus/` found by `ui/retrieval.py`
and comes back with the pages it used, so a citation can be checked by opening
the PDF at that page. This is page-level retrieval, a prototype for the chunking
and hybrid search of Steps 4-5, not a substitute for them.

Usage:
    .venv\\Scripts\\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000

Environment: OLLAMA_URL, CHAT_MODEL, CHAT_NUM_CTX, CHAT_TOP_K, CHAT_KEEP_ALIVE,
CHAT_THINK (leave at 0 for qwen3.5:4b — see D-048).
"""

from __future__ import annotations

import json
import os
import pathlib

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ui import retrieval

STATIC = pathlib.Path(__file__).parent / "static"
CORPUS = pathlib.Path("data/corpus").resolve()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
# qwen3.5 4B won the Step 2 comparison: 23/30 oracle against 18/30 for the 7B,
# faster on every latency measure, and inside D-002's 3-4B band (D-047/D-048).
MODEL = os.environ.get("CHAT_MODEL", "qwen3.5:4b")
KEEP_ALIVE = os.environ.get("CHAT_KEEP_ALIVE", "30m")
# Thinking must stay off. With it on, qwen3.5 spends the whole answer budget on
# hidden reasoning and returns an empty string, which looks like a broken model.
THINK = os.environ.get("CHAT_THINK", "0").lower() in ("1", "true", "yes")
NUM_CTX = int(os.environ.get("CHAT_NUM_CTX", "4096"))
TOP_K = int(os.environ.get("CHAT_TOP_K", "4"))

# Instructions sit after the passages on purpose: the model follows a rule that
# follows the text more reliably, and repeating the reminder next to each passage
# stops it miscounting which passage a sentence came from.
SYSTEM_RULES = (
    "Answer using only the passages above, in at most four sentences.\n"
    "After every factual sentence, put the letter of the passage it came from in"
    " square brackets, copying the letter shown next to that passage — for example"
    " [A] or [C]. Do not count passages and do not renumber them.\n"
    "Never use outside knowledge. Never invent a number, name or date.\n"
    "If the passages do not contain the answer, reply exactly NOT FOUND and then,\n"
    "on the next line, name what is missing in one short sentence."
)

app = FastAPI(title="RAG project chat", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

INDEX = retrieval.build()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    temperature: float = 0.0


# Numbers were mis-copied by the model (it answered with [2] for text that only
# passage 1 contained), so passages carry a letter and the letter maps back to a
# page here, not in the model's head.
LETTERS = "ABCDEFGH"


def key_for(position: int) -> str:
    return LETTERS[position - 1] if 0 < position <= len(LETTERS) else str(position)


class ThinkFilter:
    """Strip ` thinking...</think>` blocks from a streamed answer.

    qwen3.5 emits those tags as literal text even with `think: false` — usually
    an empty pair at the very start — so without this the UI shows "<think>".
    Tags can be split across chunks, so a partial tag at the end of a chunk is
    held back until it resolves.
    """

    OPEN = "<think>"
    CLOSE = "</think>"

    def __init__(self) -> None:
        self.pending = ""
        self.inside = False

    def feed(self, text: str) -> str:
        self.pending += text
        out: list[str] = []
        while self.pending:
            if self.inside:
                end = self.pending.find(self.CLOSE)
                if end < 0:
                    self.pending = self.pending[-(len(self.CLOSE) - 1):]
                    break
                self.pending = self.pending[end + len(self.CLOSE):]
                self.inside = False
                continue
            start = self.pending.find(self.OPEN)
            if start < 0:
                safe = len(self.pending)
                for size in range(1, len(self.OPEN)):
                    if self.pending.endswith(self.OPEN[:size]):
                        safe = len(self.pending) - size
                        break
                out.append(self.pending[:safe])
                self.pending = self.pending[safe:]
                break
            out.append(self.pending[:start])
            self.pending = self.pending[start + len(self.OPEN):]
            self.inside = True
        return "".join(out)

    def flush(self) -> str:
        rest, self.pending = self.pending, ""
        return "" if self.inside else rest


def build_system(hits: list[dict]) -> str:
    if not hits:
        return "No passage matched this question.\n\n" + SYSTEM_RULES
    blocks = []
    for i, hit in enumerate(hits, start=1):
        key = key_for(i)
        blocks.append(
            f"PASSAGE [{key}] — {hit['label']}, page {hit['page']}\n"
            f"{hit['context']}\n"
            f"(End of passage [{key}]: anything taken from here is cited as [{key}].)"
        )
    return "\n\n".join(blocks) + "\n\n" + SYSTEM_RULES


def public_sources(hits: list[dict]) -> list[dict]:
    return [{"n": i, "key": key_for(i), "doc": h["doc"], "page": h["page"],
             "label": h["label"], "score": h["score"], "snippet": h["snippet"],
             "ocr": bool(h.get("ocr"))}
            for i, h in enumerate(hits, start=1)]


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    try:
        with httpx.Client(timeout=5) as client:
            tags = client.get(f"{OLLAMA_URL}/api/tags").json()
            running = client.get(f"{OLLAMA_URL}/api/ps").json()
    except httpx.HTTPError as exc:
        return {"ok": False, "model": MODEL, "error": f"Ollama unreachable: {exc.__class__.__name__}"}

    names = [m.get("name", "") for m in tags.get("models", [])]
    loaded = [m for m in running.get("models", []) if m.get("name", "").startswith(MODEL)]
    return {
        "ok": any(n.startswith(MODEL) for n in names),
        "model": MODEL,
        "loaded": bool(loaded),
        "context": NUM_CTX,
        "pages": len(INDEX["pages"]),
        "documents": len(INDEX["docs"]),
        "ocr_pages": INDEX.get("ocr_pages", 0),
        "unreadable": {k: v for k, v in INDEX["unreadable"].items()},
    }


@app.get("/api/docs")
def docs() -> dict:
    return {"docs": INDEX["docs"], "unreadable": INDEX["unreadable"]}


@app.get("/pdf/{name}")
def pdf(name: str) -> FileResponse:
    """Serve a corpus PDF so a citation can open at its page (#page=N)."""
    known = {d["doc"] for d in INDEX["docs"]}
    if name not in known:
        raise HTTPException(status_code=404, detail="not a corpus document")
    path = (CORPUS / name).resolve()
    if CORPUS not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="document missing")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    question = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    hits = retrieval.search(INDEX, question, k=TOP_K)

    history = [m.model_dump() for m in payload.messages][-6:]
    messages = [{"role": "system", "content": build_system(hits)}] + history

    body = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "think": THINK,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": payload.temperature, "num_ctx": NUM_CTX},
    }
    sources = public_sources(hits)

    async def relay():
        think = ThinkFilter()
        timeout = httpx.Timeout(connect=5, read=600, write=30, pool=5)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=body) as upstream:
                    if upstream.status_code != 200:
                        detail = (await upstream.aread()).decode("utf-8", "replace")[:400]
                        yield json.dumps({"error": f"Ollama {upstream.status_code}: {detail}"}) + "\n"
                        return
                    async for line in upstream.aiter_lines():
                        if await request.is_disconnected():
                            return
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        message = chunk.get("message") or {}
                        if message.get("content"):
                            cleaned = think.feed(message["content"])
                            if not cleaned:
                                if not chunk.get("done"):
                                    continue
                            message["content"] = cleaned
                            chunk["message"] = message
                        if chunk.get("done"):
                            tail = think.flush()
                            if tail:
                                message["content"] = (message.get("content") or "") + tail
                                chunk["message"] = message
                            chunk["sources"] = sources
                        yield json.dumps(chunk) + "\n"
            except httpx.HTTPError as exc:
                yield json.dumps({"error": f"{exc.__class__.__name__}: {exc}"}) + "\n"

    return StreamingResponse(relay(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/config")
def config() -> dict:
    return {"model": MODEL, "context": NUM_CTX, "top_k": TOP_K, "endpoint": OLLAMA_URL,
            "pages": len(INDEX["pages"])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
