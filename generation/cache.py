"""Answer cache keyed by the question and everything that could invalidate it (D-017).

Four things go into the key: the question (normalised), the index version, the model
version, and the prompt version. A cached answer survives a restart — that is the point —
but it must never survive a re-parsed corpus, a different model file, or edited prompt
rules, so each of those changes the key and the old entry simply stops being found.

Normalisation is deliberately conservative: case, whitespace and trailing punctuation.
It does not stem, reorder or drop words, because "540 mm" and "540 m" are different
questions and a cached answer to one must not be served for the other.

The key alone is not enough. `index_version` is computed from the corpus signature the
index holds, which can be stale if the index was loaded before a file changed; and an
entry can outlive a page inside an otherwise unchanged file. So every entry also stores
a fingerprint of each page it relied on. `get()` re-reads those pages and treats a
removed page, an edited page, or an old entry without fingerprints as a miss. The
fingerprint is the page text for a text page (so a re-save with the same words still
verifies) and the file hash for a scanned page (where the OCR text is not the file).

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

from corpus import CORPUS, page_fingerprint

CACHE_PATH = pathlib.Path("index/answer-cache.json")


def norm_question(question: str) -> str:
    """Lowercase, collapse whitespace, drop trailing punctuation."""
    text = re.sub(r"\s+", " ", (question or "").lower()).strip()
    return text.rstrip(" ?.!;:")


def index_version(index: dict) -> str:
    """A digest of the corpus as the index sees it: name, size and mtime per document.

    `corpus.build()` stores that signature and rebuilds when it changes, so this is the
    same fact the index itself uses to decide it is stale.
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


def _sources(record: dict, corpus_root: pathlib.Path) -> list[dict]:
    """Fingerprints of the pages this answer relied on, one per distinct (doc, page)."""
    sources = []
    seen = set()
    for passage in record.get("passages") or []:
        doc, page = passage.get("doc"), passage.get("page")
        if not doc or page is None or (doc, page) in seen:
            continue
        seen.add((doc, page))
        sources.append({"doc": doc, "page": int(page),
                        "fingerprint": page_fingerprint(doc, int(page), root=corpus_root)})
    return sources


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
        prompt_version: str, path: pathlib.Path = CACHE_PATH,
        corpus_root: pathlib.Path | None = None) -> dict | None:
    """The cached answer, or None when the key is absent or a cited page changed.

    An entry written before page fingerprints existed has no `sources` field; it is a
    miss rather than an answer nobody can re-check.
    """
    record = load(path).get(key(question, index_version=index_version,
                                model_version=model_version,
                                prompt_version=prompt_version))
    if record is None:
        return None

    sources = record.get("sources")
    if sources is None:
        return None
    root = corpus_root or CORPUS
    for source in sources:
        current = page_fingerprint(source["doc"], source["page"], root=root)
        if not current or current != source["fingerprint"]:
            return None
    return {field: value for field, value in record.items() if field != "sources"}


def put(question: str, record: dict, *, index_version: str, model_version: str,
        prompt_version: str, path: pathlib.Path = CACHE_PATH,
        corpus_root: pathlib.Path | None = None) -> str:
    """Store an answer with the fingerprints `get()` will re-check."""
    root = corpus_root or CORPUS
    entry = {**record, "sources": _sources(record, root)}
    entries = load(path)
    cache_key = key(question, index_version=index_version,
                    model_version=model_version,
                    prompt_version=prompt_version)
    entries[cache_key] = entry
    save(entries, path)
    return cache_key
