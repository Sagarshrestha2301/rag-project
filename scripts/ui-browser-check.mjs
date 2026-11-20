// Browser check for the Step 7 definition of done: a "not found" answer must show the
// D-021 unreadable-pages warning with the counts `index/pages.json` holds, and the
// citation chips must be where the reader clicks them.
//
// It drives the installed Chrome over the DevTools protocol with nothing installed:
// node's built-in WebSocket, Chrome's own --headless mode. No new dependency, and no
// network beyond 127.0.0.1 (rule 6).
//
// Usage:
//   node scripts/ui-browser-check.mjs [http://127.0.0.1:8000] ["question"]
//
// Example of the output:
//   state        not_found
//   badge        ∅ not found
//   warning      19 of 851 pages, in 8 of 97 documents, still have no readable text after
//   per document 2023_annual_conservation_action_plan_… has 3 unreadable pages: 2, 8, 27
//   verdict      PASS
//
// Writes artifacts/step7/ui-browser-check.json. Exit 1 when the warning is missing or
// carries no per-document line.

import { spawn } from "node:child_process";
import { CHROME, connect, dropProfile, freshProfile, sleep, VIEWER_STATE,
         waitForJson, waitForViewer, clickViewer } from "./ui-cdp.mjs";
import { writeFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const SERVER = process.argv[2] || "http://127.0.0.1:8000";
// A question no page answers, whose top retrieved documents are ones with unreadable
// pages (2018/2023 policy PDFs, 2001 Li) - the case the warning exists for.
const QUESTION = process.argv[3] ||
  "Who chaired the annual conservation action plan 2080 workshop?";
const PORT = 9334;
const TIMEOUT_MS = Number(process.env.UI_TIMEOUT_MS || 240000);
const OUT_DIR = resolve("artifacts/step7");
const OUT = join(OUT_DIR, "ui-browser-check.json");

async function checkViewer(session) {
  const clicked = await session.evaluate(`(() => {
    const chip = [...document.querySelectorAll(".message--assistant .cite")].pop();
    if (!chip) return null;
    const info = { page: Number(chip.dataset.page || 1), doc: chip.dataset.doc || "",
                   text: (chip.dataset.text || "").slice(0, 80) };
    chip.click();
    return info;
  })()`);
  if (!clicked) return { ok: false, reason: "no chip to click" };

  const seen = await waitForViewer(session, (state) =>
    state.canvas && state.canvas.w > 0 && state.hits > 0);
  if (!seen) {
    return { ok: false, reason: "the viewer never showed a highlighted page", chip: clicked };
  }
  const pageOk = Number(seen.page) === clicked.page;

  // One page forward: the quote belongs to the cited page, so nothing is highlighted.
  const forward = await clickViewer(session, "cite-next");
  const away = forward
    ? await waitForViewer(session, (state) => Number(state.page) !== clicked.page)
    : null;
  const awayOk = Boolean(away && away.hits === 0);

  const back = awayOk ? await clickViewer(session, "cite-prev") : false;
  const again = back
    ? await waitForViewer(session, (state) =>
        Number(state.page) === clicked.page && state.hits > 0)
    : null;
  const backOk = Boolean(again);

  const closed = await session.evaluate(`(() => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    return document.querySelector(".cite-viewer").hidden;
  })()`);

  // The evidence rail opens the same viewer, from the retrieved passage rather than the
  // verified quote, so the source cards must highlight too.
  const card = await session.evaluate(`(() => {
    const node = document.querySelector("#evidence-body .source");
    if (!node) return null;
    const info = { page: Number(node.dataset.page || 1), doc: node.dataset.doc || "" };
    node.click();
    return info;
  })()`);
  const fromCard = card
    ? await waitForViewer(session, (state) => state.hits > 0 && Number(state.page) === card.page)
    : null;
  const cardOk = Boolean(fromCard);
  if (cardOk) {
    await session.evaluate(`(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return true;
    })()`);
  }

  return { ...(again || seen),
           ok: pageOk && seen.hits > 0 && awayOk && backOk && closed === true && cardOk,
           pageOk, awayOk, backOk, cardOk, awayPage: away ? away.page : null,
           cardPage: card ? card.page : null, closed: closed === true, chip: clicked };
}

const state = {
  question: QUESTION,
  server: SERVER,
  warning: null,
  status: null,
  badge: null,
  chips: [],
  consoleErrors: [],
  ok: false,
};

const profile = freshProfile("step7-chrome-");
const chrome = spawn(CHROME, [
  ...profile.args,
  `--remote-debugging-port=${PORT}`,
  SERVER + "/",
], { stdio: "ignore" });

let session;
try {
  const version = await waitForJson(`http://127.0.0.1:${PORT}/json/version`);
  state.browser = version["Browser"];
  const targets = await waitForJson(`http://127.0.0.1:${PORT}/json/list`);
  const page = targets.find((target) => target.type === "page");
  if (!page) throw new Error("no page target");
  session = await connect(page.webSocketDebuggerUrl);
  await session.send("Runtime.enable");
  await session.send("Page.enable");
  await session.send("Log.enable");
  // An explicit navigation, waited for, so no evaluate races the first load.
  await session.send("Page.navigate", { url: SERVER + "/" });
  let loaded = false;
  for (let i = 0; i < 120 && !loaded; i += 1) {
    await sleep(250);
    try {
      loaded = await session.evaluate('document.readyState === "complete"');
    } catch {
      loaded = false;
    }
  }
  if (!loaded) throw new Error("the page never finished loading");
  session.socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") {
      state.consoleErrors.push(message.params.entry.text);
    }
    if (message.method === "Runtime.exceptionThrown") {
      const detail = message.params.exceptionDetails;
      state.consoleErrors.push(detail.exception?.description || detail.text);
    }
  });

  // The page index is loaded at import time; wait for the app to have a model badge.
  const ready = await session.evaluate(`(async () => {
    for (let i = 0; i < 300; i += 1) {
      if (document.getElementById("composer-input")) return true;
      await new Promise((done) => setTimeout(done, 100));
    }
    return false;
  })()`, true);
  if (!ready) throw new Error("the composer never rendered");

  // Send the question the way the page does: value, then the input and submit events.
  await session.evaluate(`(() => {
    const input = document.getElementById("composer-input");
    input.value = ${JSON.stringify(QUESTION)};
    input.dispatchEvent(new Event("input", { bubbles: true }));
    document.getElementById("composer-form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    return true;
  })()`);

  const settled = await session.evaluate(`(async () => {
    const started = Date.now();
    while (Date.now() - started < ${TIMEOUT_MS}) {
      const messages = [...document.querySelectorAll(".message--assistant")];
      const last = messages[messages.length - 1];
      if (last && last.dataset.state && last.dataset.state !== "streaming") {
        return last.dataset.state;
      }
      await new Promise((done) => setTimeout(done, 250));
    }
    return "timeout";
  })()`, true);
  state.status = settled;
  if (settled === "timeout") {
    state.debug = await session.evaluate(`(() => ({
      messages: document.querySelectorAll(".message").length,
      assistants: [...document.querySelectorAll(".message--assistant")]
        .map((node) => node.dataset.state || "none"),
      status: (document.getElementById("chat-status") || {}).textContent,
      text: (document.getElementById("thread") || {}).innerText || "",
    }))()`);
    throw new Error("the answer never settled: " + JSON.stringify(state.debug));
  }

  // The evidence rail is a toggle, not something an answer opens (owner, 2026-11-20):
  // most readers never need it. The check opens it the way a reader does, so the source
  // cards it then inspects exist at all.
  state.railHiddenAfterAnswer = await session.evaluate(
    'document.getElementById("app").classList.contains("app--evidence-hidden")');
  await session.evaluate(`(() => {
    const button = document.querySelector('#app [data-action="toggle-evidence"]');
    if (button) button.click();
    return Boolean(button);
  })()`);

  const dom = await session.evaluate(`(() => {
    const message = [...document.querySelectorAll(".message--assistant")].pop();
    const badge = message ? message.querySelector(".state-badge") : null;
    const warning = message ? message.querySelector(".unreadable-warning") : null;
    const body = warning ? warning.querySelector(".unreadable-warning__body") : null;
    const title = warning ? warning.querySelector(".unreadable-warning__title") : null;
    // The warning used to read "Some pages cannot be read8 of 97 documents..." because
    // the title and the counts were one inline run. They must be separate lines.
    const layout = title && body ? {
      titleDisplay: getComputedStyle(title).display,
      titleBottom: Math.round(title.getBoundingClientRect().bottom),
      bodyTop: Math.round(body.getBoundingClientRect().top),
    } : null;
    const items = warning
      ? [...warning.querySelectorAll(".unreadable-warning__list li")].map((li) => li.textContent)
      : [];
    const chips = [...document.querySelectorAll(".message--assistant .cite")].map((chip) => ({
      n: chip.dataset.n || null,
      text: chip.textContent.trim(),
      doc: chip.dataset.doc || null,
      disabled: chip.classList.contains("cite--disabled"),
      title: chip.title,
    }));
    // The printed citation line is a reference block, and the marker inside it must stay
    // plain text: it is the same source the evidence rail already lists.
    const refs = [...document.querySelectorAll(".message--assistant .message__ref")]
      .map((node) => node.textContent.trim().slice(0, 160));
    const chipsInRefs = document.querySelectorAll(".message--assistant .message__ref .cite").length;
    // D-066: the rail names the work (authors, year, title), not the storage file.
    const sourceList = [...document.querySelectorAll("#evidence-body .source")].map((node) => ({
      label: ((node.querySelector(".source__label") || {}).textContent || "").trim(),
      meta: ((node.querySelector(".source__meta") || {}).textContent || "").trim(),
    }));
    return {
      badge: badge ? badge.textContent.trim() : null,
      warningTitle: title ? title.textContent.trim() : null,
      warningBody: body ? body.textContent.trim() : null,
      warningLayout: layout,
      warningItems: items,
      chips,
      refs,
      chipsInRefs,
      sourceList,
      answer: message ? (message.querySelector(".message__body") || {}).textContent : null,
    };
  })()`);

  state.badge = dom.badge;
  state.warning = dom.warningBody || dom.warningTitle
    ? { title: dom.warningTitle, body: dom.warningBody, items: dom.warningItems,
        layout: dom.warningLayout }
    : null;
  state.chips = dom.chips;
  state.refs = dom.refs;
  state.chipsInRefs = dom.chipsInRefs;
  state.sources = dom.sourceList;
  state.answer = (dom.answer || "").trim().slice(0, 200);
  // An unanswerable question must show the warning; an answered one must show chips that
  // still read `[n]`, because a bare `1` looks like part of a number.
  if (settled === "not_found") {
    const layout = (state.warning || {}).layout || {};
    // The two counts are different page sets: 19 pages stayed empty after OCR, 86 pages
    // OCR did read. The body must say both, and not merge them into one clause.
    const body = (state.warning || {}).body || "";
    state.ok = Boolean(state.warning && state.warning.items.length &&
      state.warning.title === "Some pages cannot be read" &&
      body.includes("still have no readable text after OCR") &&
      body.includes("pages were read by OCR") &&
      layout.bodyTop >= layout.titleBottom - 1 &&
      state.railHiddenAfterAnswer === true);
  } else {
    state.ok = state.chips.length > 0 &&
      state.chips.every((chip) => chip.text === `[${chip.n}]` && Boolean(chip.doc)) &&
      state.refs.length > 0 && state.chipsInRefs === 0 &&
      state.railHiddenAfterAnswer === true;
  }

  // The citation viewer: the chip opens the cited page with the quoted passage
  // highlighted, and Escape closes it. pdf.js has to load and render for this to pass.
  if (state.chips.length) state.viewer = await checkViewer(session);
  if (state.viewer) state.ok = state.ok && state.viewer.ok;
} finally {
  try { if (session) session.socket.close(); } catch { /* already closed */ }

  chrome.kill();
  await sleep(300);
  dropProfile(profile.dir);
}

mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT, JSON.stringify(state, null, 1));

console.log(`browser      ${state.browser || "unknown"}`);
console.log(`question     ${state.question}`);
console.log(`state        ${state.status}`);
console.log(`badge        ${state.badge}`);
console.log(`warning      ${state.warning ? state.warning.title : "MISSING"}`);
if (state.warning) {
  const layout = state.warning.layout || {};
  console.log(`warning body ${state.warning.body}`);
  console.log(`warning flow title ${layout.titleDisplay}, title bottom ${layout.titleBottom}px, `
    + `body top ${layout.bodyTop}px`);
}
for (const item of state.warning ? state.warning.items : []) console.log(`per document ${item}`);
console.log(`rail         ${state.railHiddenAfterAnswer ? "hidden after the answer, opened by its toggle" : "OPENED ITSELF after the answer"}`);
console.log(`chips        ${state.chips.length}  ${state.chips.map((chip) => chip.text).join(" ")}`);
for (const ref of state.refs || []) console.log(`reference    ${ref.slice(0, 110)}`);
console.log(`chips in refs ${state.chipsInRefs}`);
for (const source of state.sources || []) {
  console.log(`source       ${source.label.slice(0, 100)} | ${source.meta}`);
}
if (state.viewer) {
  const viewer = state.viewer;
  const chip = viewer.chip || {};
  console.log(`viewer       ${viewer.ok ? "open" : "FAILED"}  ` +
    `${viewer.title || viewer.reason || ""} | ${viewer.meta || ""}`);
  if (viewer.canvas) {
    console.log(`viewer page  ${viewer.page} (chip says ${chip.page}) · canvas ` +
      `${viewer.canvas.w}x${viewer.canvas.h} · highlights ${viewer.hits}`);
    console.log(`viewer text  ${viewer.hitText}`);
    if (viewer.note) console.log(`viewer note  ${viewer.note}`);
    console.log(`viewer nav   page ${viewer.chip.page} with a highlight, page ` +
      `${viewer.awayPage} without one, back ${viewer.backOk ? "yes" : "no"}`);
    console.log(`viewer card  source card opens page ${viewer.cardPage} with ` +
      `${viewer.cardOk ? "a highlight" : "NO highlight"}`);
    console.log(`viewer closed ${viewer.closed}`);
  }
}
console.log(`console errors ${state.consoleErrors.length}`);
console.log(`verdict      ${state.ok ? "PASS" : "FAIL"}  (${OUT})`);
process.exit(state.ok ? 0 : 1);
