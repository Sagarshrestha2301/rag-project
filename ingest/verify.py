"""Step 3 checks: table cells against the PDF's own words, a page review sheet,
and throughput.

Two things this never does: it does not re-run the parsers (it reads what was
written), and it does not "fix" a mismatch — a mismatch is the finding.

Usage:
    .venv\\Scripts\\python.exe -m ingest.cli verify
"""

from __future__ import annotations

import json
import pathlib
import random

import pymupdf

from ingest import tables

OUT = pathlib.Path("artifacts/step3")
PARSED = pathlib.Path("index/parsed")


def load() -> tuple[list[dict], list[dict], dict]:
    pages = [json.loads(line) for line in
             (PARSED / "pages.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    found = [json.loads(line) for line in
             (PARSED / "tables.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads((PARSED / "manifest.json").read_text(encoding="utf-8"))
    return pages, found, manifest


def _page_words(doc: str, page_no: int) -> set[str]:
    with pymupdf.open(pathlib.Path("data/corpus") / doc) as pdf:
        return {w[4] for w in pdf[page_no - 1].get_text("words")}


def check_tables(found: list[dict]) -> dict:
    """Every numeric token in a table must exist verbatim in that page's words.

    The page's word list is the source of truth: if a token is not there, the
    assembler invented it, and that is the failure this check exists to catch.
    """
    total = matched = 0
    problems: list[str] = []
    per_doc: dict[str, dict] = {}
    cache: dict[tuple[str, int], set[str]] = {}

    for entry in found:
        table = tables.Table(rows=entry["rows"], bbox=tuple(entry["bbox"]),
                             parser=entry["parser"], notes=entry["notes"])
        key = (entry["doc"], entry["pdf_page"])
        if key not in cache:
            cache[key] = _page_words(*key)
        words = cache[key]

        numbers = tables.numeric_cells(table)
        bucket = per_doc.setdefault(entry["doc"], {"tables": 0, "numeric": 0, "matched": 0})
        bucket["tables"] += 1
        bucket["numeric"] += len(numbers)
        for token in numbers:
            total += 1
            if token in words:
                matched += 1
                bucket["matched"] += 1
            else:
                problems.append(f"{entry['doc']} p{entry['pdf_page']} table {entry['table']}: "
                                f"{token!r} not in the page's words")

    return {"tables": len(found), "numeric_tokens": total, "matched": matched,
            "problems": problems, "per_doc": per_doc}


def throughput(manifest: dict) -> dict:
    """Rates that match what was actually measured.

    `table_seconds` is the cost of *detecting* tables on every text page, not the
    cost of the 7 table pages — reporting it as a table-page rate would be a
    number that means nothing. Whole-run rate is the honest extrapolation base.
    """
    docs = manifest["docs"]
    pages = sum(d["pages"] for d in docs)
    text_pages = sum(d["text_pages"] for d in docs)
    table_pages = sum(len(d["table_pages"]) for d in docs)
    ocr_pages = sum(d["ocr_pages"] for d in docs)
    detection_seconds = sum(d["table_seconds"] for d in docs)
    total_seconds = sum(d["seconds"] for d in docs)
    extract_seconds = max(total_seconds - detection_seconds, 1e-6)
    per_minute = pages / max(total_seconds, 1e-6) * 60

    return {
        "pages": pages, "text_pages": text_pages, "table_pages": table_pages,
        "ocr_pages": ocr_pages, "total_seconds": round(total_seconds, 1),
        "detection_seconds": round(detection_seconds, 1),
        "detection_ms_per_page": round(detection_seconds / max(text_pages, 1) * 1000),
        "pages_per_minute": round(per_minute, 1),
        "text_pages_per_min": round(text_pages / extract_seconds * 60, 1),
        "ocr_seconds_per_page": round(
            (total_seconds - extract_seconds) / ocr_pages, 1) if ocr_pages else None,
        "hours_for_100k_pages": round(100_000 / max(per_minute, 1e-6) / 60, 1),
    }


def review_html(pages: list[dict], sample_size: int = 20, seed: int = 7) -> pathlib.Path:
    """A page to check PDF page numbers against the viewer, by eye."""
    rng = random.Random(seed)
    picked = rng.sample(pages, min(sample_size, len(pages)))
    picked.sort(key=lambda p: (p["doc"], p["pdf_page"]))

    rows = []
    for page in picked:
        anchor = f"/pdf/{page['doc']}#page={page['pdf_page']}"
        first = page["text"][:110].replace("<", "&lt;")
        rows.append(
            "<tr>"
            f"<td>{page['doc'][:46]}</td>"
            f"<td class='num'>{page['pdf_page']}</td>"
            f"<td class='num'>{page['printed_label'] or '—'}</td>"
            f"<td>{page['parser']}{' · OCR' if page['ocr'] else ''}</td>"
            f"<td class='snip'>{first}…</td>"
            f"<td><a href='{anchor}' target='_blank'>open</a></td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Step 3 — page number check</title>
<style>
 body{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:32px;color:#1a1a1a}}
 h1{{font-size:19px;margin:0 0 4px}} p{{color:#555;margin:0 0 18px}}
 table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #e5e5e5;vertical-align:top}}
 th{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#777}}
 .num{{font-variant-numeric:tabular-nums;font-family:ui-monospace,Consolas,monospace}}
 .snip{{color:#444;font-size:12.5px;max-width:520px}}
 a{{color:#0b62d6}}
</style></head><body>
<h1>Step 3 — page number check</h1>
<p>{len(picked)} pages sampled from {len(pages)}. “PDF page” is the index the eval uses;
“printed” is the number visible on the page. Open each PDF at that page and confirm the
text on the right is what you see.</p>
<table><thead><tr><th>Document</th><th>PDF page</th><th>Printed</th><th>Parser</th><th>Opening text</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "review.html"
    path.write_text(html, encoding="utf-8")
    return path


def write_report(tables_report: dict, speed: dict, manifest: dict) -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Step 3 report (generated)", ""]
    totals = manifest["totals"]
    lines += [
        f"- Documents: **{totals['documents']}**, pages: **{totals['pages']}**, "
        f"tables: **{totals['tables']}**, OCR pages: **{totals['ocr_pages']}**, "
        f"unreadable: **{totals['unreadable_pages']}**",
        f"- Parse time: **{speed['total_seconds']} s** for {speed['pages']} pages = "
        f"**{speed['pages_per_minute']} pages/min**",
        f"- Table detection costs **{speed['detection_seconds']} s** over "
        f"{speed['text_pages']} pages ({speed['detection_ms_per_page']} ms/page, run on every "
        f"page); text extraction without it: {speed['text_pages_per_min']} pages/min",
        f"- OCR: {speed['ocr_pages']} pages, {speed['ocr_seconds_per_page']} s/page"
        if speed["ocr_seconds_per_page"] else "- OCR: none in this run",
        f"- Extrapolation at the measured whole-run rate: "
        f"**{speed['hours_for_100k_pages']} h for 100k pages**",
        "",
        "## Table cell check",
        "",
        f"- Tables: **{tables_report['tables']}**",
        f"- Numeric tokens: **{tables_report['numeric_tokens']}**, matched against the page's "
        f"own words: **{tables_report['matched']}**",
        "",
    ]
    if tables_report["problems"]:
        lines.append("Mismatches:")
        lines += [f"- {p}" for p in tables_report["problems"]]
    else:
        lines.append("No numeric token differed from the page's word list.")
    lines += ["", "## Per document", "",
              "| Document | Tables | Numeric tokens | Matched |", "|---|---|---|---|"]
    for doc, stats in tables_report["per_doc"].items():
        lines.append(f"| {doc[:44]} | {stats['tables']} | {stats['numeric']} | {stats['matched']} |")

    path = OUT / "report.md"
    body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")

    # The step names this path explicitly, so keep a copy there too.
    named = pathlib.Path("reports/parsing-sample.md")
    named.parent.mkdir(parents=True, exist_ok=True)
    named.write_text(body, encoding="utf-8")
    return path
