"""Local UI server: the Step 6 pipeline, localhost only, no external request.

Every answer comes from `generation.answer` through `ui/pipeline.py` -- router,
condensation, cache, retrieval, gate, prompt, verifier and the one retry are the code
`eval/` measures (D-061). The server adds transport only: an NDJSON event stream, the
`debug_version` 1 payload, the corpus PDF route and the static files. It has no prompt
of its own; if this file grows answer logic again, the eval and the reader diverge.

Usage:
    .venv\\Scripts\\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000

Environment: OLLAMA_URL, CHAT_MODEL, CHAT_NUM_CTX, CHAT_KEEP_ALIVE, CHAT_THINK.

Event stream on `POST /api/chat` (one JSON object per line):
    {"event": "start", "model": {...}}
    {"event": "token", "text": "540 mm"}
    {"event": "done",  "payload": {...}}   # ui/SPEC.md section 7
    {"event": "error", "message": "..."}
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

from generation import answer as generator
from ui import pipeline

STATIC = pathlib.Path(__file__).parent / "static"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = generator.MODEL
NUM_CTX = generator.NUM_CTX

# Every asset is local, so the browser is told it may not fetch anything else: no CDN,
# no webfont, and no direct call to Ollama. The policy is the rule, not the convention
# (ui/SPEC.md section 9).
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

app = FastAPI(title="Local RAG chat", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    temperature: float = generator.TEMPERATURE
    use_cache: bool = True


@app.middleware("http")
async def local_only_headers(request: Request, call_next):
    """Add the CSP to every response, including static files and PDFs."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    source = pipeline.index()
    try:
        with httpx.Client(timeout=5) as client:
            tags = client.get(f"{OLLAMA_URL}/api/tags").json()
            running = client.get(f"{OLLAMA_URL}/api/ps").json()
    except httpx.HTTPError as exc:
        return {"ok": False, "model": MODEL,
                "error": f"Ollama unreachable: {exc.__class__.__name__}"}

    names = [m.get("name", "") for m in tags.get("models", [])]
    loaded = [m for m in running.get("models", []) if m.get("name", "").startswith(MODEL)]
    return {
        "ok": any(n.startswith(MODEL) for n in names),
        "model": MODEL,
        "loaded": bool(loaded),
        "context": NUM_CTX,
        "prompt_version": generator.prompt.PROMPT_VERSION,
        "pages": len(source["pages"]),
        "documents": len(source["docs"]),
        "ocr_pages": source.get("ocr_pages", 0),
        "unreadable": {k: v for k, v in (source.get("unreadable") or {}).items()},
    }


@app.get("/api/docs")
def docs() -> dict:
    source = pipeline.index()
    return {"docs": source["docs"], "unreadable": source.get("unreadable") or {}}


@app.get("/pdf/{name}")
def pdf(name: str) -> FileResponse:
    """Serve a corpus PDF so a citation opens at its page (#page=N)."""
    path = pipeline.pdf_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="not a corpus document")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{path.name}"'})


@app.post("/api/chat")
def chat(payload: ChatRequest) -> StreamingResponse:
    """Answer the last user turn, streaming the pipeline's events as NDJSON.

    No disconnect polling in the generator: `request.is_disconnected()` is a coroutine,
    and a plain `if` on its return value was always true, which truncated every stream
    to zero events. Starlette closes this generator when the client goes away, and the
    worker thread in `pipeline.stream` is a daemon, so the model call simply finishes
    into nothing.
    """
    messages = [m.model_dump() for m in payload.messages]
    question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    history = messages[:-1][-6:] if messages else []

    def relay():
        try:
            for event in pipeline.stream(question, history, use_cache=payload.use_cache):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:  # noqa: BLE001 - the browser must see the failure
            yield json.dumps({"event": "error",
                              "message": f"{exc.__class__.__name__}: {exc}"}) + "\n"

    return StreamingResponse(relay(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/config")
def config() -> dict:
    source = pipeline.index()
    return {"model": MODEL, "context": NUM_CTX, "prompt_version": generator.prompt.PROMPT_VERSION,
            "temperature": generator.TEMPERATURE, "pages": len(source["pages"])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
