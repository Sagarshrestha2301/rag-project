"""Answer cache keyed by the question and everything that could invalidate it (D-017).

Four things go into the key: the question (normalised), the index version, the model
version, and the prompt version. A cached answer survives a restart — that is the point —
but it must never survive a re-parsed corpus, a different model file, or edited prompt
rules, so each of those changes the key and the old entry simply stops being found.

Normalisation is deliberately conservative: case, whitespace and trailing punctuation.
It does not stem, reorder or drop words, because "540 mm" and "540 m" are different
questions and a cached answer to one must not be served for the other.

Usage:
    from generation import cache
    version = cache.index_version(index)
    hit = cache.get(question, index_version=version, model_version="qwen3.5:4b:abc123",
                    prompt_version=prompt.PROMPT_VERSION)
    if hit is None:
        ...  # answer, then cache.put(...)
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

CACHE_PATH = pathlib.Path("index/answer-cache.json")


def norm_question(question: str) -> str:
    """Lowercase, collapse whitespace, drop trailing punctuation."""
    text = re.sub(r"\s+", " ", (question or "").lower()).strip()
    return text.rstrip(" ?.!;:")


def index_version(index: dict) -> str:
    """A digest of the corpus as the index sees it: name, size and mtime per document.

    `ui.retrieval.build()` already stores that signature and rebuilds when it changes,
    so this is the same fact the index itself uses to decide it is stale.
    """
    signature = index.get("signature") or []
    payload = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def model_version(name: str, digest: str | None = None) -> str:
    """`name:digest` when Ollama reports one, otherwise just the name.

    The digest is what makes the key follow the weights rather than the tag: re-pulling
    `qwen3.5:4b` at a new build must not serve answers produced by the old one.
    """
    return f"{name}:{digest[:12]}" if digest else name


def key(question: str, *, index_version: str, model_version: str,
        prompt_version: str) -> str:
    payload = json.dumps([norm_question(question), index_version, model_version,
                          prompt_version], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def load(path: pathlib.Path = CACHE_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save(entries: dict, path: pathlib.Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")


def get(question: str, *, index_version: str, model_version: str,
        prompt_version: str, path: pathlib.Path = CACHE_PATH) -> dict | None:
    return load(path).get(key(question, index_version=index_version,
                              model_version=model_version,
                              prompt_version=prompt_version))


def put(question: str, record: dict, *, index_version: str, model_version: str,
        prompt_version: str, path: pathlib.Path = CACHE_PATH) -> str:
    entries = load(path)
    cache_key = key(question, index_version=index_version, model_version=model_version,
                    prompt_version=prompt_version)
    entries[cache_key] = record
    save(entries, path)
    return cache_key
