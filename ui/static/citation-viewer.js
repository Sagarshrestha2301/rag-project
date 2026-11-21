/* Citation viewer: the cited PDF page, with the cited text highlighted.
 *
 * Frontend only. It reads the PDF from the endpoint the UI already has (`/pdf/<doc>`),
 * so no server, pipeline, prompt or index code is involved, and it draws its highlight
 * from the page's own text layer rather than from any stored offset.
 *
 * Usage (app.js does exactly this, if the component loaded):
 *   window.CitationViewer.open({ doc: "1970_Marahatta_....pdf", page: 2,
 *                                text: "The 24-hour rainfall depth of 540 mm at Tistung",
 *                                title: "Marahatta & Bhusal (2009)" })
 *   window.CitationViewer.close()
 *
 * `text` is the passage the answer quoted for that page (the source snippet). It is
 * matched against the page text after normalising case and punctuation, and only the
 * part of it that is actually printed is highlighted; a quote the page does not carry
 * (an OCR'd page whose text differs, or a paraphrase) reports "no match" instead of
 * highlighting the wrong words.
 *
 * pdf.js is imported on the first click, not on page load, and it is served from
 * `ui/static/vendor/pdfjs/` - no CDN, no network beyond 127.0.0.1 (rule 6).
 */

const PDFJS_SRC = "/static/vendor/pdfjs/pdf.min.mjs";
const WORKER_SRC = "/static/vendor/pdfjs/pdf.worker.min.mjs";

// Keep at most this many open PDFDocuments: each holds the parsed file in memory.
const MAX_OPEN_DOCUMENTS = 3;

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.2;

let pdfjs = null;            // the imported module
const documents = new Map(); // doc name -> { pdf, pages }
let ui = null;               // the built modal
let renderToken = 0;         // bumped per render, so a stale render cannot paint
let zoom = 1;
let totalPages = 1;          // from the open document; `go()` clamps against it
let current = { doc: "", page: 1, quotePage: 1, text: "", title: "" };

/* ------------------------------------------------------------------ pdf.js */

async function loadPdfjs() {
  if (!pdfjs) {
    pdfjs = await import(PDFJS_SRC);
    pdfjs.GlobalWorkerOptions.workerSrc = WORKER_SRC;
  }
  return pdfjs;
}

async function documentFor(name) {
  if (documents.has(name)) {
    const held = documents.get(name);
    documents.delete(name);            // refresh insertion order (LRU)
    documents.set(name, held);
    return held;
  }
  const lib = await loadPdfjs();
  const pdf = await lib.getDocument({
    url: `/pdf/${encodeURIComponent(name)}`,
    // The corpus has no embedded JavaScript to run and nothing to fetch: pdf.js only
    // needs the file itself, which the CSP already permits from this origin.
    isEvalSupported: false,
    disableAutoFetch: true,
  }).promise;
  const held = { pdf, pages: new Map() };
  documents.set(name, held);
  while (documents.size > MAX_OPEN_DOCUMENTS) {
    const [oldest, closed] = documents.entries().next().value;
    documents.delete(oldest);
    closed.pdf.destroy().catch(() => {});
  }
  return held;
}

async function pageFor(held, number) {
  if (!held.pages.has(number)) held.pages.set(number, await held.pdf.getPage(number));
  return held.pages.get(number);
}

/* --------------------------------------------------------------- the shell */

function build() {
  const root = document.createElement("div");
  root.className = "cite-viewer";
  root.hidden = true;
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-label", "Cited page");

  const backdrop = document.createElement("div");
  backdrop.className = "cite-viewer__backdrop";
  backdrop.dataset.action = "cite-close";

  const panel = document.createElement("div");
  panel.className = "cite-viewer__panel";

  const bar = document.createElement("header");
  bar.className = "cite-viewer__bar";

  const titles = document.createElement("div");
  titles.className = "cite-viewer__titles";
  const title = document.createElement("p");
  title.className = "cite-viewer__title";
  const meta = document.createElement("p");
  meta.className = "cite-viewer__meta";
  titles.append(title, meta);

  const nav = document.createElement("div");
  nav.className = "cite-viewer__nav";
  const prev = button("cite-prev", "‹", "Previous page", "cite-viewer__step");
  const pageInput = document.createElement("input");
  pageInput.className = "cite-viewer__page";
  pageInput.type = "text";
  pageInput.inputMode = "numeric";
  pageInput.setAttribute("aria-label", "Page number");
  const total = document.createElement("span");
  total.className = "cite-viewer__total";
  const next = button("cite-next", "›", "Next page", "cite-viewer__step");
  nav.append(prev, pageInput, total, next);

  const zoomOut = button("cite-zoom-out", "−", "Zoom out", "cite-viewer__step");
  const zoomIn = button("cite-zoom-in", "+", "Zoom in", "cite-viewer__step");

  const open = document.createElement("a");
  open.className = "cite-viewer__open";
  open.target = "_blank";
  open.rel = "noopener";
  open.textContent = "Open original PDF";
  open.title = "Open the original PDF in a new tab at this page";
  const close = button("cite-close", "✕", "Close", "cite-viewer__close");

  bar.append(titles, nav, zoomOut, zoomIn, open, close);

  const stage = document.createElement("div");
  stage.className = "cite-viewer__stage";

  const page = document.createElement("div");
  page.className = "cite-viewer__page-wrap";
  const canvas = document.createElement("canvas");
  canvas.className = "cite-viewer__canvas";
  const layer = document.createElement("div");
  layer.className = "cite-viewer__text textLayer";
  const marks = document.createElement("div");
  marks.className = "cite-viewer__marks";
  const note = document.createElement("p");
  note.className = "cite-viewer__note";
  page.append(canvas, marks, layer, note);
  stage.append(page);

  panel.append(bar, stage);
  root.append(backdrop, panel);
  document.body.append(root);

  root.addEventListener("click", onClick);
  document.addEventListener("keydown", onKeydown);

  return { root, panel, stage, page, canvas, layer, note, title, meta, pageInput, total,
           prev, next, open };
}

function button(action, label, title, cls) {
  const node = document.createElement("button");
  node.type = "button";
  node.className = cls;
  node.dataset.action = action;
  node.textContent = label;
  node.title = title;
  node.setAttribute("aria-label", title);
  return node;
}

/* ------------------------------------------------------------- the actions */

function onClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target || !ui || !target.closest(".cite-viewer")) return;
  const action = target.dataset.action;
  if (action === "cite-close") { close(); return; }
  if (action === "cite-prev") { go(current.page - 1); return; }
  if (action === "cite-next") { go(current.page + 1); return; }
  if (action === "cite-zoom-in") { zoomBy(ZOOM_STEP); return; }
  if (action === "cite-zoom-out") { zoomBy(-ZOOM_STEP); return; }
}

function onKeydown(event) {
  if (!ui || ui.root.hidden) return;
  if (event.key === "Escape") { event.preventDefault(); close(); }
  else if (event.key === "ArrowLeft" && event.target.tagName !== "INPUT") go(current.page - 1);
  else if (event.key === "ArrowRight" && event.target.tagName !== "INPUT") go(current.page + 1);
}

function go(number) {
  const next = Math.min(Math.max(1, number), Math.max(1, totalPages));
  if (next === current.page) return;
  current.page = next;
  render();
}

function zoomBy(delta) {
  zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round((zoom + delta) * 100) / 100));
  render({ keepZoom: true });
}

/* ---------------------------------------------------------------- rendering */

async function render({ keepZoom = false } = {}) {
  const token = ++renderToken;
  const { doc, page } = current;
  ui.note.textContent = "";
  ui.note.hidden = true;
  if (!keepZoom) zoom = 1;

  let held;
  try {
    held = await documentFor(doc);
  } catch (error) {
    ui.note.hidden = false;
    ui.note.textContent = `The PDF could not be opened (${error.message}). ` +
      "Use “Open original PDF” to read it in the browser's viewer.";
    return;
  }
  if (token !== renderToken) return;

  totalPages = held.pdf.numPages;
  ui.total.textContent = `/ ${totalPages}`;
  ui.pageInput.value = String(page);
  ui.prev.disabled = page <= 1;
  ui.next.disabled = page >= totalPages;
  ui.open.href = `/pdf/${encodeURIComponent(doc)}#page=${page}`;
  ui.meta.textContent = `page ${page} of ${totalPages}` +
    (current.text ? " · looking for the cited text" : "");

  let pdfPage;
  try {
    pdfPage = await pageFor(held, page);
  } catch (error) {
    ui.note.hidden = false;
    ui.note.textContent = `This page could not be read (${error.message}).`;
    return;
  }
  if (token !== renderToken) return;

  const base = pdfPage.getViewport({ scale: 1 });
  const available = Math.max(320, ui.stage.clientWidth - 48);
  const fit = Math.min(1.8, Math.max(0.6, available / base.width));
  const viewport = pdfPage.getViewport({ scale: fit * zoom });

  const ratio = window.devicePixelRatio || 1;
  ui.canvas.width = Math.floor(viewport.width * ratio);
  ui.canvas.height = Math.floor(viewport.height * ratio);
  ui.canvas.style.width = `${Math.floor(viewport.width)}px`;
  ui.canvas.style.height = `${Math.floor(viewport.height)}px`;
  ui.page.style.width = `${Math.floor(viewport.width)}px`;
  ui.page.style.height = `${Math.floor(viewport.height)}px`;
  ui.layer.replaceChildren();
  ui.layer.style.width = `${Math.floor(viewport.width)}px`;
  ui.layer.style.height = `${Math.floor(viewport.height)}px`;
  ui.layer.style.setProperty("--scale-factor", String(viewport.scale));

  const context = ui.canvas.getContext("2d");
  await pdfPage.render({ canvasContext: context, viewport, transform:
    ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] }).promise;
  if (token !== renderToken) return;

  const lib = await loadPdfjs();
  const textLayer = new lib.TextLayer({
    textContentSource: pdfPage.streamTextContent(),
    container: ui.layer,
    viewport,
  });
  await textLayer.render();
  if (token !== renderToken) return;

  const hits = highlight(ui.layer, current.text);
  if (current.text) {
    ui.meta.textContent = `page ${page} of ${totalPages} · ` +
      (hits.matched
        ? `${hits.count} highlight${hits.count === 1 ? "" : "s"}`
        : page === current.quotePage ? "cited text not found on this page" : "no highlight here");
  }
  if (hits.first) hits.first.scrollIntoView({ block: "center" });
  else ui.stage.scrollTop = 0;
}

/* -------------------------------------------------------------- highlighting */

/** Lowercase, and every run of non-alphanumerics becomes one space. */
function normalise(text) {
  return String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Every word in the text layer, in reading order, with its exact node and offsets. */
function pageWords(container) {
  const words = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const value = (node.nodeValue || "").toLowerCase();
    for (const match of value.matchAll(/[a-z0-9]+/g)) {
      words.push({ text: match[0], node, start: match.index,
                   end: match.index + match[0].length });
    }
  }
  return words;
}

/**
 * Align the quote's words with the page's, tolerating the two ways a quotation stops being
 * a substring of the text layer: pdf.js can split a token (`20` + `th`, `24` + `-` + `hour`)
 * and a quote can contain words the page breaks differently. Walks both lists in order and
 * accepts the longest run that keeps at least `MIN_COVERAGE` of the quote's words.
 *
 * Returns the index of the first and last page word covered, or null.
 */
const MIN_COVERAGE = 0.75;

function align(quote, words) {
  for (let start = 0; start < words.length; start += 1) {
    let i = start;
    let j = 0;
    let last = -1;
    while (i < words.length && j < quote.length) {
      const page = words[i].text;
      const next = words[i + 1] ? words[i + 1].text : "";
      const wanted = quote[j];
      const wantedPair = wanted + (quote[j + 1] || "");
      if (page === wanted) { last = i; i += 1; j += 1; continue; }
      if (page + next === wanted) { last = i + 1; i += 2; j += 1; continue; }
      if (page === wantedPair) { last = i; i += 1; j += 2; continue; }
      break;
    }
    const covered = j >= Math.max(2, Math.ceil(quote.length * MIN_COVERAGE));
    if (last >= 0 && covered && j > 0) return { start, end: last, words: j };
  }
  return null;
}

function highlight(container, quote) {
  const box = container.parentElement.querySelector(".cite-viewer__marks");
  box.replaceChildren();
  if (!quote) return { matched: false, count: 0, first: null };

  const words = pageWords(container);
  const quoteWords = normalise(quote).split(" ").filter(Boolean);
  if (!quoteWords.length) return { matched: false, count: 0, first: null };
  const found = align(quoteWords, words);
  if (!found) return { matched: false, count: 0, first: null, words: 0 };

  // One range over the start of the first matched word to the end of the last: it crosses
  // text nodes for free, and `getClientRects` gives one rectangle per line it covers, so
  // the highlight is the printed words and nothing is rewritten in the text layer.
  const range = document.createRange();
  range.setStart(words[found.start].node, words[found.start].start);
  range.setEnd(words[found.end].node, words[found.end].end);

  const frame = box.getBoundingClientRect();
  let count = 0;
  let first = null;
  for (const rect of range.getClientRects()) {
    if (rect.width < 1 || rect.height < 1) continue;
    const mark = document.createElement("div");
    mark.className = "cite-viewer__hit";
    mark.style.left = `${rect.left - frame.left}px`;
    mark.style.top = `${rect.top - frame.top}px`;
    mark.style.width = `${rect.width}px`;
    mark.style.height = `${rect.height}px`;
    box.append(mark);
    count += 1;
    first = first || mark;
    if (count > 60) break;      // a runaway match paints no useful extra highlight
  }
  if (!count) return { matched: false, count: 0, first: null, words: found.words };
  box.dataset.quote = words.slice(found.start, found.end + 1)
    .map((word) => word.text).join(" ");
  return { matched: true, count, first, words: found.words };
}

/* ---------------------------------------------------------------- the API */

function show(payload) {
  if (!ui) {
    ui = build();
    ui.pageInput.addEventListener("change", () => go(Number(ui.pageInput.value) || 1));
    ui.pageInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); go(Number(ui.pageInput.value) || 1); }
    });
    window.addEventListener("resize", () => { if (!ui.root.hidden) render({ keepZoom: true }); });
  }
  const restored = document.activeElement;
  ui.restoreFocus = restored instanceof HTMLElement ? restored : null;
  document.body.classList.add("cite-viewer-open");
  ui.root.hidden = false;
  ui.title.textContent = payload.title || payload.doc;
  ui.title.title = payload.doc;
  ui.pageInput.value = String(payload.page || 1);
  ui.meta.textContent = `page ${payload.page || 1}`;
  ui.layer.replaceChildren();
  ui.note.hidden = true;
  render();
  (ui.root.querySelector(".cite-viewer__close") || ui.root).focus();
}

function close() {
  if (!ui || ui.root.hidden) return;
  renderToken += 1;
  ui.root.hidden = true;
  document.body.classList.remove("cite-viewer-open");
  if (ui.restoreFocus && document.contains(ui.restoreFocus)) ui.restoreFocus.focus();
}

const CitationViewer = {
  open({ doc, page = 1, text = "", title = "" } = {}) {
    if (!doc) return false;
    current = { doc, page: Number(page) || 1, quotePage: Number(page) || 1, text, title };
    show(current);
    return true;
  },
  close,
  get isOpen() { return Boolean(ui && !ui.root.hidden); },
};

window.CitationViewer = CitationViewer;
export default CitationViewer;
