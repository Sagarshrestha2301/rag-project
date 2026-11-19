"""Answer cache: keyed on what invalidates it, re-checked against the pages it cited.

Four things go into the key: the question (normalised), the index version, the model
version and the prompt version (D-017). A cached answer survives a restart — that is the
point — but it must never survive a re-parsed corpus, a different model file or edited
prompt rules, so each of those changes the key and the old entry stops being found.

The key has one blind spot, so there is a second guard: the index version is a hash of
file names, sizes and mtimes, which does not change when the same files are parsed into
different text (a re-OCR, a changed extractor) or when a page disappears from a rebuilt
index. Each entry therefore stores a hash of the text of every page the answer relied on,
and a hit re-hashes those pages from the index it was handed. That is five short string
hashes — no PDF is opened and no path is resolved — and it checks the text retrieval and
the quote verifier actually read, which for a scanned page is the OCR text, not the file.

Normalisation is deliberately conservative: case, whitespace and trailing punctuation.
It does not stem, reorder or drop words, because "540 mm" and "540 m" are different
questions and a cached answer to one must not be served for the other.

Usage:
    from generation import cache
    hit = cache.get(question, index=index, model_version="qwen3.5:4b:abc123",
                    prompt_version=prompt.PROMPT_VERSION)
    if hit is None:
        ...  # answer, then cache.put(..., index=index)
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

from corpus import CORPUS, ROOT, is_current

# Absolute, like `corpus.CORPUS`: a question asked from another folder must find the same
# answers, not start a second cache beside it.
CACHE_PATH = ROOT / "index" / "answer-cache.json"

Page = tuple[str, int]


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
        prompt_version: str, search_question: str | None = None) -> str:
    """The cache key: the question asked, the question searched, and the three versions.

    Both questions, because a follow-up is rewritten before it is searched and the two
    can differ. Keying only on the rewritten text let a follow-up that the condenser
    turned back into the previous question replay that question's stored answer
    (measured 2026-11-19: a question about the Bagmati's flood-prone area was served the
    Tistung rainfall answer, marked `cached`).
    """
    payload = json.dumps([norm_question(question), norm_question(search_question or question),
                          index_version, model_version, prompt_version],
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _page_hashes(pages: list[dict]) -> dict[Page, str]:
    """{(doc, page): hash of the page's text as the index stores it}.

    A page with no text is left out rather than hashed: the hash of "" would look like a
    fingerprint and make an answer that quotes nothing checkable a permanent hit.
    """
    hashes = {}
    for page in pages or []:
        text = page.get("text") or ""
        if text.strip():
            hashes[(str(page["doc"]), int(page["page"]))] = \
                hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    return hashes


def _sources(record: dict, hashes: dict[Page, str]) -> list[dict]:
    """The pages this answer relied on, one entry per distinct page.

    A page with no text in the index gets an empty fingerprint on purpose, so the entry
    can never be served: an answer that cannot be re-checked is not a hit.
    """
    sources, seen = [], set()
    for passage in record.get("passages") or []:
        if not passage.get("doc") or passage.get("page") is None:
            continue
        page = (str(passage["doc"]), int(passage["page"]))
        if page in seen:
            continue
        seen.add(page)
        sources.append({"doc": page[0], "page": page[1],
                        "fingerprint": hashes.get(page, "")})
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


def get(question: str, *, index: dict, model_version: str, prompt_version: str,
        search_question: str | None = None,
        root: pathlib.Path | None = None, path: pathlib.Path = CACHE_PATH) -> dict | None:
    """The cached answer, or None when the key is absent or a cited page changed.

    `index` is the page index this process is answering from, and it must still describe
    the corpus on disk: a long-lived process holding an index from before an edit is a
    miss even when every page it quotes is unchanged, because retrieval and the verifier
    would be reading text the files no longer contain. An entry written before page
    fingerprints existed has no `sources` field; it is a miss rather than an answer nobody
    can re-check.
    """
    record = load(path).get(key(question, index_version=index_version(index),
                                model_version=model_version,
                                prompt_version=prompt_version,
                                search_question=search_question))
    if record is None:
        return None

    sources = record.get("sources")
    if sources is None:
        return None

    if not is_current(index, root or CORPUS):
        return None

    current = _page_hashes(index.get("pages") or [])
    for source in sources:
        stored = source.get("fingerprint")
        if not stored or current.get((source["doc"], source["page"])) != stored:
            return None
    return {field: value for field, value in record.items() if field != "sources"}


def put(question: str, record: dict, *, index: dict, model_version: str,
        prompt_version: str, search_question: str | None = None,
        path: pathlib.Path = CACHE_PATH) -> str:
    """Store an answer with the page fingerprints `get()` will re-check."""
    entries = load(path)
    cache_key = key(question, index_version=index_version(index),
                    model_version=model_version,
                    prompt_version=prompt_version,
                    search_question=search_question)
    entries[cache_key] = {**record,
                          "sources": _sources(record, _page_hashes(index.get("pages") or []))}
    save(entries, path)
    return cache_key
