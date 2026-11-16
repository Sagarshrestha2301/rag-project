"""Owner inspection sheet: 10 chunks, 3 of them tables (Step 4 verification).

The sheet prints each chunk exactly as it is stored, so the prefix, the page
range and the section path can be compared with the PDF page it cites. Three of
the ten are table chunks, because those carry the fields the text chunks do not
(caption, units, footnotes).

Usage:
    .venv\\Scripts\\python.exe -m chunk.review
Output:
    artifacts/step4/review.html
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from corpus import path_for as corpus_path      # noqa: E402

CHUNKS = pathlib.Path("index/chunks.jsonl")
OUT = pathlib.Path("artifacts/step4/review.html")


def load(path: pathlib.Path = CHUNKS) -> list[dict]:
    """Every chunk record from `index/chunks.jsonl`."""
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m chunk.cli build` first")
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pick(pool: list[dict], count: int, rng: random.Random,
          used: set[str]) -> list[dict]:
    """`count` chunks from as many different documents as the pool allows."""
    by_doc: dict[str, list[dict]] = {}
    for chunk in pool:
        by_doc.setdefault(chunk["file"], []).append(chunk)
    fresh = sorted(name for name in by_doc if name not in used)
    rng.shuffle(fresh)
    picked = [rng.choice(by_doc[name]) for name in fresh[:count]]
    if len(picked) < count:
        # Only when the pool has fewer documents than the sample needs: take the
        # remaining chunks at random, so a document can contribute twice rather
        # than the sheet silently returning fewer than it promises.
        taken = {chunk["chunk_id"] for chunk in picked}
        rest = [chunk for chunk in pool if chunk["chunk_id"] not in taken]
        rng.shuffle(rest)
        picked += rest[:count - len(picked)]
    return picked


def sample(chunks: list[dict], n: int = 10, tables: int = 3,
           seed: int = 7) -> list[dict]:
    """`tables` table chunks plus the rest text chunks, deterministically.

    The same `(chunks, n, tables, seed)` always returns the same chunks, so a
    reviewer and a later run look at the same ten records.
    """
    if tables > n:
        raise ValueError(f"cannot pick {tables} tables out of {n} chunks")
    rng = random.Random(seed)
    table_pool = [c for c in chunks if c["type"] == "table"]
    text_pool = [c for c in chunks if c["type"] != "table"]
    if len(table_pool) < tables:
        raise ValueError(f"need {tables} table chunks, found {len(table_pool)}")

    picked = _pick(table_pool, tables, rng, used=set())
    used = {c["file"] for c in picked}
    picked += _pick(text_pool, n - tables, rng, used)
    picked.sort(key=lambda c: (c["file"], c["page_start"], c["chunk_id"]))
    return picked


def _link(chunk: dict) -> str:
    """A `file://` link to the chunk's first page, or "" if the PDF is missing."""
    try:
        target = corpus_path(chunk["file"]).resolve()
    except FileNotFoundError:
        return ""
    return target.as_uri() + f"#page={chunk['page_start']}"


def write_html(picked: list[dict], path: pathlib.Path = OUT) -> pathlib.Path:
    """Write the review sheet and return its path."""
    blocks = []
    for chunk in picked:
        link = _link(chunk)
        pages = (f"p{chunk['page_start']}" if chunk["page_start"] == chunk["page_end"]
                 else f"p{chunk['page_start']}-{chunk['page_end']}")
        section = " → ".join(chunk["section_path"]) or "(no section headings)"
        fields = [
            ("type", chunk["type"]),
            ("section", f"{section}  [{chunk['section_path_source']}]"),
            ("year", str(chunk["year"]) if chunk["year"] else "—"),
            ("publisher", chunk["publisher"] or "—"),
            ("doc_type", chunk["doc_type"] or "—"),
            ("OCR", "yes" if chunk["ocr"] else "no"),
            ("chunker", chunk["chunker_version"]),
        ]
        rows = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
                       for k, v in fields)
        extra = ""
        if chunk["type"] == "table":
            notes = "; ".join(chunk["notes"]) or "—"
            footnotes = " | ".join(chunk["footnotes"]) or "—"
            extra = (
                f"<dt>caption</dt><dd>{html.escape(chunk['caption'] or '—')}</dd>"
                f"<dt>units</dt><dd>{html.escape(chunk['units'] or '—')}</dd>"
                f"<dt>footnotes</dt><dd>{html.escape(footnotes)}</dd>"
                f"<dt>notes</dt><dd>{html.escape(notes)}</dd>")
        opened = (f"<a href='{link}' target='_blank'>open the PDF page</a>" if link
                  else "<span class='warn'>PDF not found under data/corpus</span>")
        blocks.append(
            f"<section><h2>{html.escape(chunk['file'][:70])} <span>{pages}</span></h2>"
            f"<p class='meta'>{chunk['chunk_id']} · {opened}</p>"
            f"<dl>{rows}{extra}</dl>"
            f"<p class='ctx'><b>doc_context:</b> {html.escape(chunk['doc_context'] or '—')}</p>"
            f"<pre class='text'>{html.escape(chunk['text'])}</pre></section>")

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Step 4 — chunk inspection</title>
<style>
 body{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:32px;color:#1a1a1a;max-width:1000px}}
 h1{{font-size:19px;margin:0 0 4px}} h2{{font-size:15px;margin:0 0 2px}}
 h2 span{{color:#888;font-weight:400}} p{{color:#555;margin:0 0 8px}}
 section{{border-top:1px solid #e5e5e5;padding-top:16px;margin-top:22px}}
 dl{{display:grid;grid-template-columns:110px 1fr;gap:2px 10px;margin:8px 0;font-size:13px}}
 dt{{color:#777}} dd{{margin:0}}
 pre.text{{background:#f7f7f7;border:1px solid #e5e5e5;padding:10px;white-space:pre-wrap;
   font:12.5px/1.55 Consolas,monospace;margin:8px 0 0}}
 .ctx{{font-size:13px}} a{{color:#0b62d6}} .warn{{color:#b00}}
</style></head><body>
<h1>Step 4 — chunk inspection</h1>
<p>{len(picked)} chunks, {sum(1 for c in picked if c['type'] == 'table')} of them tables,
from {len({c['file'] for c in picked})} documents. The text below is stored as shown;
open each PDF page and check the text, the page numbers and the section path.</p>
{''.join(blocks)}
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(prog="chunk.review")
    parser.add_argument("--chunks", default=str(CHUNKS))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    chunks = load(pathlib.Path(args.chunks))
    picked = sample(chunks, seed=args.seed)
    path = write_html(picked, pathlib.Path(args.out))
    tables = sum(1 for chunk in picked if chunk["type"] == "table")
    print(f"{len(picked)} chunks ({tables} tables) from "
          f"{len({chunk['file'] for chunk in picked})} documents")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
