"""Build a static side-by-side review page for the eval set.

For every question it renders the cited corpus page to PNG and shows the
question, gold answer, gold quote and page image next to each other, so the
owner can approve or reject each question against the actual source.

This is a review aid for Step 1, not the Step 7 web UI: no server, no framework,
one generated HTML file.

Page images are embedded as base64 data URIs, so the single HTML file works on
its own (a sibling image folder is not served by a single-file preview).

Usage:
    .venv\\Scripts\\python.exe eval\\build_review.py
Output:
    eval/review.html  (gitignored)
"""

from __future__ import annotations

import base64
import html
import json
import pathlib

import pymupdf

QUESTIONS = pathlib.Path("eval/questions.jsonl")
OUT_HTML = pathlib.Path("eval/review.html")

CSS = """
:root { --ink:#1f2933; --muted:#6b7785; --line:#d9e2ec; --bg:#f7f9fb; --accent:#2b6cb0; }
* { box-sizing: border-box; }
body { margin:0; font-family: Segoe UI, system-ui, sans-serif; color:var(--ink); background:var(--bg); }
.review__header { position:sticky; top:0; z-index:5; background:#fff; border-bottom:1px solid var(--line); padding:14px 22px; }
.review__title { margin:0 0 4px; font-size:17px; }
.review__meta { color:var(--muted); font-size:13px; }
.review__filters { margin-top:10px; display:flex; gap:8px; flex-wrap:wrap; }
.review__filter { border:1px solid var(--line); background:#fff; border-radius:14px; padding:5px 12px; font-size:13px; cursor:pointer; color:var(--ink); }
.review__filter--active { background:var(--accent); border-color:var(--accent); color:#fff; }
.review__list { padding:18px 22px 80px; display:flex; flex-direction:column; gap:16px; }
.question { background:#fff; border:1px solid var(--line); border-radius:8px; display:grid; grid-template-columns: minmax(320px,1fr) minmax(320px,1fr); gap:0; overflow:hidden; }
.question--hidden { display:none; }
.question__body { padding:14px 16px; }
.question__id { font-family: Consolas, monospace; font-size:12px; color:var(--muted); }
.question__badge { display:inline-block; font-size:11px; text-transform:uppercase; letter-spacing:.04em; padding:2px 7px; border-radius:10px; margin-left:6px; }
.question__badge--dev { background:#e3f0ff; color:#1c4f8a; }
.question__badge--heldout { background:#ffe8d6; color:#8a4b12; }
.question__badge--notfound { background:#fde2e1; color:#8a1c1c; }
.question__text { font-size:15px; margin:8px 0 10px; line-height:1.45; }
.question__label { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-top:10px; }
.question__gold { font-weight:600; }
.question__quote { background:var(--bg); border-left:3px solid var(--accent); padding:8px 10px; font-size:13px; line-height:1.45; font-family: Consolas, monospace; }
.question__approve { margin-top:12px; display:flex; align-items:center; gap:7px; font-size:13px; }
.question__source { border-left:1px solid var(--line); background:#fbfcfd; display:flex; flex-direction:column; }
.question__source-label { padding:8px 12px; font-size:12px; color:var(--muted); border-bottom:1px solid var(--line); }
.question__page { width:100%; height:420px; overflow:auto; }
.question__page img { width:100%; display:block; }
.review__footer { position:fixed; bottom:0; left:0; right:0; background:#fff; border-top:1px solid var(--line); padding:10px 22px; display:flex; gap:12px; align-items:center; font-size:13px; }
.review__button { border:1px solid var(--accent); background:var(--accent); color:#fff; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:13px; }
.review__count { color:var(--muted); }
"""

JS = """
(() => {
  const list = document.querySelector('.review__list');
  const filters = document.querySelectorAll('.review__filter');
  const count = document.querySelector('.review__count');
  const copyBtn = document.querySelector('.review__button');

  const visible = () => [...document.querySelectorAll('.question:not(.question--hidden)')];
  const approved = () => [...document.querySelectorAll('.question__check:checked')].map(c => c.dataset.qid);
  const refresh = () => {
    count.textContent = approved().length + ' approved of ' + document.querySelectorAll('.question').length
      + ' (' + visible().length + ' shown)';
  };

  filters.forEach(btn => btn.addEventListener('click', () => {
    filters.forEach(b => b.classList.toggle('review__filter--active', b === btn));
    const f = btn.dataset.filter;
    document.querySelectorAll('.question').forEach(card => {
      const show = f === 'all' || card.dataset.split === f || card.dataset.type === f || (f === 'notfound' && card.dataset.type === 'notfound');
      card.classList.toggle('question--hidden', !show);
    });
    refresh();
  }));

  list.addEventListener('change', e => {
    if (e.target.classList.contains('question__check')) refresh();
  });

  copyBtn.addEventListener('click', async () => {
    const ids = approved();
    try { await navigator.clipboard.writeText(ids.join(', ')); copyBtn.textContent = 'Copied ' + ids.length + ' ids'; }
    catch { window.prompt('Copy these ids:', ids.join(', ')); }
    setTimeout(() => { copyBtn.textContent = 'Copy approved ids'; }, 2000);
  });

  refresh();
})();
"""


def main() -> int:
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]

    images: dict[str, str] = {}
    cards = []
    for r in rows:
        src = r["gold_sources"][0]
        key = f"{pathlib.Path(src['file']).stem[:24]}-p{src['page']}".replace(" ", "_")
        if key not in images:
            doc = pymupdf.open(src["file"])
            pix = doc[src["page"] - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2))
            doc.close()
            images[key] = "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode("ascii")
        img = key

        split_cls = "dev" if r["split"] == "dev" else "heldout"
        nf = "" if r["answerable"] else '<span class="question__badge question__badge--notfound">not found</span>'
        quote = html.escape(r["gold_quote"]) if r["gold_quote"] else "<em>no quote: the answer must be absent from the corpus</em>"
        cards.append(f"""
      <article class="question" data-split="{r['split']}" data-type="{r['type']}">
        <div class="question__body">
          <div>
            <span class="question__id">{html.escape(r['id'])}</span>
            <span class="question__badge question__badge--{split_cls}">{r['split']}</span>
            <span class="question__badge">{html.escape(r['type'])}</span>{nf}
          </div>
          <div class="question__text">{html.escape(r['question'])}</div>
          <div class="question__label">gold answer</div>
          <div class="question__gold">{html.escape(r['gold_answer']) if r['gold_answer'] else '&mdash; (must answer "not found")'}</div>
          <div class="question__label">gold quote (verified against the page text)</div>
          <div class="question__quote">{quote}</div>
          <label class="question__approve">
            <input type="checkbox" class="question__check" data-qid="{html.escape(r['id'])}">
            approve this question
          </label>
        </div>
        <div class="question__source">
          <div class="question__source-label">page {src['page']} of {html.escape(pathlib.Path(src['file']).name[:46])}</div>
          <div class="question__page"><img data-page="{img}" alt="page {src['page']}"></div>
        </div>
      </article>""")

    filters = [("all", "All"), ("dev", "Dev"), ("heldout", "Held-out"), ("table", "Table"),
               ("notfound", "Not found"), ("comparison", "Comparison"), ("summary", "Summary")]
    filter_html = "".join(
        f'<button class="review__filter{" review__filter--active" if k == "all" else ""}" data-filter="{k}">{html.escape(label)}</button>'
        for k, label in filters)

    OUT_HTML.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eval set review - step 1</title>
<style>{CSS}</style>
</head>
<body>
  <header class="review__header">
    <h1 class="review__title">Eval set review &mdash; {len(rows)} questions</h1>
    <div class="review__meta">Tick the questions you approve, then copy the ids. Gold pages are physical PDF pages; the image on the right is that page.</div>
    <div class="review__filters">{filter_html}</div>
  </header>
  <main class="review__list">{''.join(cards)}
  </main>
  <footer class="review__footer">
    <span class="review__count"></span>
    <button class="review__button">Copy approved ids</button>
  </footer>
  <script>const PAGE_IMAGES = {json.dumps(images)};
document.querySelectorAll('img[data-page]').forEach(img => {{ img.src = PAGE_IMAGES[img.dataset.page]; }});</script>
  <script>{JS}</script>
</body>
</html>
""", encoding="utf-8")

    size_mb = OUT_HTML.stat().st_size / 1e6
    print(f"wrote {OUT_HTML} with {len(rows)} questions and {len(images)} unique embedded page images ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
