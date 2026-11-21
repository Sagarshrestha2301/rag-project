// Browser check for the empty state: every starter card must answer, and every citation
// chip under that answer must open the cited page with the quote highlighted.
//
// The step-7 check (`ui-browser-check.mjs`) drives one question; this one drives the four
// cards a reader actually sees first, so a card the corpus cannot answer (or a chip that
// opens nothing) fails the check instead of the reader's first click.
//
// Usage:
//   node scripts/ui-starters-check.mjs [http://127.0.0.1:8000]
//
// Example of the output:
//   card 1  verified  chips 2  viewer 2/2  "What was the 24-hour rainfall at Tistung..."
//   verdict PASS  (artifacts/step9/ui-starters-check.json)
//
// Exit 1 when a card does not answer or a chip opens no highlighted page.

import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

import { CHROME, connect, dropProfile, freshProfile, sleep, VIEWER_STATE,
         waitForJson, waitForViewer } from "./ui-cdp.mjs";

const SERVER = process.argv[2] || "http://127.0.0.1:8000";
const PORT = 9335;
const TIMEOUT_MS = Number(process.env.UI_TIMEOUT_MS || 240000);
const OUT_DIR = "artifacts/step9";
const OUT = `${OUT_DIR}/ui-starters-check.json`;

const findPage = async () => {
  for (let i = 0; i < 100; i += 1) {
    const targets = await waitForJson(`http://127.0.0.1:${PORT}/json/list`);
    const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
    if (page) return page;
    await sleep(200);
  }
  throw new Error("Chrome opened no page target");
};

/** How many starter cards exist, once `app.js` is actually listening for the clicks.
 *
 * The cards are in the static HTML, so counting them says nothing about whether the
 * module has run: a first run clicked card 1 during load, nothing was sent, and the check
 * timed out. The badge only changes after `boot()` fetched `/api/health`, which is after
 * the delegated click handler is attached.
 */
const cardsReady = async (session) => {
  for (let i = 0; i < 300; i += 1) {
    const seen = await session.evaluate(`(() => {
      const badge = (document.getElementById("model-badge") || {}).textContent || "";
      const blank = !badge.trim() || badge.trim() === "qwen3.5 4B";
      return { count: document.querySelectorAll(".empty__card").length, ready: !blank };
    })()`).catch(() => ({ count: 0, ready: false }));
    if (seen.count > 0 && seen.ready) return seen.count;
    await sleep(200);
  }
  return 0;
};

/** A fresh conversation, so the empty state (and its cards) comes back. */
const newChat = async (session) => {
  await session.evaluate(`(() => {
    const button = document.querySelector('[data-action="new-chat"]');
    if (button) button.click();
    return Boolean(button);
  })()`);
  return cardsReady(session);
};

const sendCard = async (session, index) => session.evaluate(`(() => {
  const card = [...document.querySelectorAll(".empty__card")][${index}];
  if (!card) return null;
  const text = card.textContent.trim();
  card.click();
  return text;
})()`);

const settle = async (session) => session.evaluate(`(async () => {
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

const readChips = async (session) => session.evaluate(`(() => {
  const chips = [...document.querySelectorAll(".message--assistant .cite")];
  return chips.map((chip, index) => ({
    index,
    n: chip.dataset.n || null,
    page: Number(chip.dataset.page || 0),
    doc: chip.dataset.doc || "",
    text: chip.textContent.trim(),
    disabled: chip.classList.contains("cite--disabled"),
    inReference: Boolean(chip.closest(".message__ref")),
  }));
})()`);

const clickChip = async (session, index) => session.evaluate(`(() => {
  const chip = [...document.querySelectorAll(".message--assistant .cite")][${index}];
  if (!chip) return false;
  chip.click();
  return true;
})()`);

const readReferences = async (session) => session.evaluate(`(() => {
  const lines = [...document.querySelectorAll(".message--assistant .message__ref-link")];
  return lines.map((line, index) => ({
    index,
    page: Number(line.dataset.page || 0),
    doc: line.dataset.doc || "",
    text: line.textContent.trim(),
    hasQuote: Boolean((line.dataset.text || "").trim()),
  }));
})()`);

const clickReference = async (session, index) => session.evaluate(`(() => {
  const line = [...document.querySelectorAll(".message--assistant .message__ref-link")][${index}];
  if (!line) return false;
  line.click();
  return true;
})()`);

const viewerOpen = (session) => session.evaluate(`(() => {
  const link = document.querySelector(".cite-viewer__open");
  return link ? { href: link.getAttribute("href") || "",
                  label: link.textContent.trim() } : null;
})()`);

const closeViewer = async (session) => {
  await session.evaluate(`(() => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    return true;
  })()`);
  for (let i = 0; i < 40; i += 1) {
    const seen = await session.evaluate(VIEWER_STATE);
    if (!seen) return true;
    await sleep(150);
  }
  return false;
};

const state = { server: SERVER, cards: [], consoleErrors: [], ok: false };
const profile = freshProfile("step9-starters-");
const chrome = spawn(CHROME, [...profile.args, `--remote-debugging-port=${PORT}`,
  `${SERVER}/`], { stdio: "ignore" });

let session;
try {
  const page = await findPage();
  session = await connect(page.webSocketDebuggerUrl);
  await session.send("Page.enable");
  await session.send("Log.enable");
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

  const count = await cardsReady(session);
  if (!count) throw new Error("the empty state never showed its cards");

  for (let index = 0; index < count; index += 1) {
    const card = { index: index + 1, question: null, status: null, chips: [], opened: 0,
                   failed: [] };
    if (index > 0 && !(await newChat(session))) {
      card.failed.push("the empty state did not come back for a new chat");
      state.cards.push(card);
      continue;
    }
    card.question = await sendCard(session, index);
    if (!card.question) {
      card.failed.push("the card did not send");
      state.cards.push(card);
      continue;
    }
    card.status = await settle(session);
    card.chips = await readChips(session);
    card.answer = await session.evaluate(
      '(([...document.querySelectorAll(".message--assistant")].pop() || {}).innerText || "")'
        + '.slice(0, 240)');

    for (const chip of card.chips) {
      if (chip.inReference) {
        card.failed.push(`chip ${chip.text} sits inside the reference block`);
        continue;
      }
      if (chip.disabled) continue;                      // a page with no readable text
      if (!(await clickChip(session, chip.index))) {
        card.failed.push(`chip ${chip.text} could not be clicked`);
        continue;
      }
      const seen = await waitForViewer(session,
        (view) => view.hits > 0 && Number(view.page) === chip.page);
      if (seen) card.opened += 1;
      else card.failed.push(`chip ${chip.text} opened no highlighted page ${chip.page}`);
      if (!(await closeViewer(session))) card.failed.push("the viewer did not close");
    }

    // The reference line under the answer is a control too (owner, 2026-11-21): the
    // whole line opens its cited page in the same viewer, with the quote highlighted.
    card.references = await readReferences(session);
    if (!card.references.length) {
      card.failed.push("the answer carries no clickable reference line");
    }
    for (const reference of card.references) {
      if (!(await clickReference(session, reference.index))) {
        card.failed.push(`reference ${reference.index + 1} could not be clicked`);
        continue;
      }
      const seen = await waitForViewer(session,
        (view) => Number(view.page) === reference.page && view.hits > 0);
      if (!seen) {
        card.failed.push(`reference line opened no highlighted page ${reference.page}`);
      } else {
        const link = await viewerOpen(session);
        if (!link || !link.href.endsWith(`#page=${reference.page}`)) {
          card.failed.push(`reference viewer does not offer the original PDF at page ${reference.page}`);
        } else if (link.label !== "Open original PDF") {
          card.failed.push(`the original-PDF button reads "${link.label}"`);
        } else {
          card.openedReferences = (card.openedReferences || 0) + 1;
        }
      }
      if (!(await closeViewer(session))) card.failed.push("the viewer did not close");
    }

    if (card.status !== "verified") card.failed.push(`the answer settled as ${card.status}`);
    if (!card.chips.length) card.failed.push("the answer carries no citation chip");
    state.cards.push(card);
  }
} finally {
  try { if (session) session.socket.close(); } catch { /* already closed */ }
  chrome.kill();
  await sleep(300);
  dropProfile(profile.dir);
}

state.ok = state.cards.length > 0 && state.cards.every((card) => !card.failed.length);
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT, JSON.stringify(state, null, 1));

for (const card of state.cards) {
  const chips = card.chips.length;
  const references = (card.references || []).length;
  console.log(`card ${card.index}  ${card.status || "no answer"}  chips ${chips}  `
    + `viewer ${card.opened}/${chips}  references ${card.openedReferences || 0}/${references}  `
    + `"${(card.question || "").slice(0, 70)}"`);
  for (const problem of card.failed) console.log(`  ! ${problem}`);
}
console.log(`console errors ${state.consoleErrors.length}`);
console.log(`verdict ${state.ok ? "PASS" : "FAIL"}  (${OUT})`);
process.exit(state.ok ? 0 : 1);
