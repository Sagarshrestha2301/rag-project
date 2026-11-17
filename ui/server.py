"""Local chat UI server: `generation.answer`, localhost only, offline.

Every answer uses the same routed, verified pipeline as the generation eval. The chat
route returns its final record in the existing newline-delimited response shape; token
streaming is Step 7 task 2.

Usage:
    .venv\\Scripts\\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000

Environment: OLLAMA_URL, CHAT_MODEL, CHAT_NUM_CTX, CHAT_THINK (see D-048).
"""

from __future__ import annotations

import asyncio
import json
import pathlib

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from corpus import CORPUS, build as build_pages, snippet, tokens
from generation import answer as generation

STATIC = pathlib.Path(__file__).parent / "static"
# `corpus.CORPUS` is absolute and project-relative, so the PDF route below serves the
# same files whether the server was started from the project root or anywhere else.
OLLAMA_URL = generation.OLLAMA_URL
MODEL = generation.MODEL
NUM_CTX = generation.NUM_CTX
TOP_K = generation.router.SETTINGS["normal"]["k"]

app = FastAPI(title="RAG project chat", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

INDEX = build_pages()
PAGE_BY_ID = {(page["doc"], page["page"]): page for page in INDEX["pages"]}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    temperature: float = 0.0


def public_sources(passages: list[dict], question: str) -> list[dict]:
    """Adapt evaluated passages to the source shape used by the existing client."""
    query = tokens(question)
    sources = []
    for passage in passages:
        page = PAGE_BY_ID.get((passage["doc"], passage["page"]))
        if page is None:
            raise RuntimeError(
                f"generation returned a passage outside the page index: "
                f"{passage['doc']} page {passage['page']}")
        number = passage["n"]
        sources.append({
            "n": number,
            "key": str(number),
            "doc": passage["doc"],
            "page": passage["page"],
            "label": passage["label"],
            "score": passage["score"],
            "snippet": snippet(page["text"], query),
            "ocr": page.get("source") == "ocr",
        })
    return sources


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


def corpus_by_name() -> dict[str, pathlib.Path]:
    """{file name: resolved path} for the whole corpus, subfolders included.

    The corpus mirrors `data/raw`'s folders (D-030), so 92 of 97 PDFs sit one or
    two levels down and `CORPUS / name` finds nothing for them — clicking a
    citation on any of those papers returned 404 until this map existed.
    """
    found: dict[str, pathlib.Path] = {}
    for path in sorted(CORPUS.rglob("*.pdf")):
        if path.name in found:
            print(f"[ui.server] duplicate corpus name, keeping the first: {path.name}")
            continue
        found[path.name] = path.resolve()
    return found


BY_NAME = corpus_by_name()


@app.get("/pdf/{name}")
def pdf(name: str) -> FileResponse:
    """Serve a corpus PDF so a citation can open at its page (#page=N)."""
    path = BY_NAME.get(name)
    if path is None or CORPUS not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="not a corpus document")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> StreamingResponse:
    user_positions = [i for i, message in enumerate(payload.messages)
                      if message.role == "user"]
    question_position = user_positions[-1] if user_positions else len(payload.messages)
    question = (payload.messages[question_position].content
                if user_positions else "")
    history = [message.model_dump()
               for message in payload.messages[:question_position]][-6:]

    try:
        record = await asyncio.to_thread(
            generation.answer, question, index=INDEX, model=MODEL,
            temperature=payload.temperature, history=history or None)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Generation failed ({exc.__class__.__name__}): {exc}",
        ) from exc

    timing = record.get("timing") or {}
    chunk = {
        "message": {"role": "assistant", "content": record["answer"]},
        "done": True,
        "total_duration": int(record["seconds"] * 1e9),
        "eval_duration": 0,
        "prompt_eval_count": timing.get("prompt_tokens"),
        "eval_count": timing.get("answer_tokens"),
        "status": record["status"],
        "cached": record["cached"],
        "record": record,
        "sources": public_sources(record["passages"], record["search_question"]),
    }

    async def relay():
        yield json.dumps(chunk, ensure_ascii=False) + "\n"

    return StreamingResponse(relay(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/config")
def config() -> dict:
    return {"model": MODEL, "context": NUM_CTX, "top_k": TOP_K, "endpoint": OLLAMA_URL,
            "pages": len(INDEX["pages"])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
