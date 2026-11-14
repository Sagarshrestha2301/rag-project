"""Local chat UI server (localhost only, offline).

Serves the single-page UI and proxies chat requests to Ollama, so the browser
never talks to a third party and CORS stays out of the picture.

This is a working chat surface, not yet the Step 7 product UI: there is no
retrieval, because no index exists until Steps 4-6. Answers come from the model
alone, so they can be wrong — they are not grounded in data/corpus/.

Usage:
    .venv\\Scripts\\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000

Point it at a different model or server:
    $env:CHAT_MODEL = "qwen2.5"; $env:OLLAMA_URL = "http://127.0.0.1:11434"
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

STATIC = pathlib.Path(__file__).parent / "static"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("CHAT_MODEL", "qwen2.5")
KEEP_ALIVE = os.environ.get("CHAT_KEEP_ALIVE", "30m")
NUM_CTX = int(os.environ.get("CHAT_NUM_CTX", "4096"))

app = FastAPI(title="RAG project chat", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    temperature: float = 0.0


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    """Report whether Ollama is reachable and which model answers."""
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
        "installed": names,
        "loaded": bool(loaded),
        "context": NUM_CTX,
    }


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    """Stream Ollama's NDJSON straight through, one JSON object per line."""
    body = {
        "model": MODEL,
        "messages": [m.model_dump() for m in payload.messages],
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": payload.temperature, "num_ctx": NUM_CTX},
    }

    async def relay():
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
                        if line.strip():
                            yield line + "\n"
            except httpx.HTTPError as exc:
                yield json.dumps({"error": f"{exc.__class__.__name__}: {exc}"}) + "\n"

    return StreamingResponse(relay(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/config")
def config() -> dict:
    """Small, non-secret runtime facts for the UI footer."""
    return {"model": MODEL, "context": NUM_CTX, "endpoint": OLLAMA_URL}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
