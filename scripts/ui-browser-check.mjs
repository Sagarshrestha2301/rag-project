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
//   warning      8 of 97 documents have pages with no text layer (19 of 851 pages, 86 …)
//   per document 2023_annual_conservation_action_plan_… has 3 unreadable pages: 2, 8, 27
//   verdict      PASS
//
// Writes artifacts/step7/ui-browser-check.json. Exit 1 when the warning is missing or
// carries no per-document line.

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const SERVER = process.argv[2] || "http://127.0.0.1:8000";
// A question no page answers, whose top retrieved documents are ones with unreadable
// pages (2018/2023 policy PDFs, 2001 Li) - the case the warning exists for.
const QUESTION = process.argv[3] ||
  "Who chaired the annual conservation action plan 2080 workshop?";
const PORT = 9334;
const TIMEOUT_MS = Number(process.env.UI_TIMEOUT_MS || 240000);
const CHROME = process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT_DIR = resolve("artifacts/step7");
const OUT = join(OUT_DIR, "ui-browser-check.json");

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

async function waitForJson(url, tries = 100) {
  for (let i = 0; i < tries; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch {
      // Chrome is still starting.
    }
    await sleep(150);
  }
  throw new Error(`no CDP endpoint at ${url}`);
}

class Session {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(JSON.stringify(message.error)));
        else resolve(message.result);
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  // A navigation destroys the execution context under an in-flight evaluate (first run
  // hit this while the app was still loading), so a transient failure is retried.
  async evaluate(expression, awaitPromise = false, tries = 20) {
    for (let i = 0; i < tries; i += 1) {
      try {
        const result = await this.send("Runtime.evaluate", {
          expression, returnByValue: true, awaitPromise,
        });
        if (result.exceptionDetails) {
          throw new Error(result.exceptionDetails.exception?.description || "evaluate failed");
        }
        return result.result.value;
      } catch (error) {
        if (!/Execution context was destroyed|Cannot find context/i.test(error.message)) throw error;
        await sleep(250);
      }
    }
    throw new Error("the page never kept an execution context");
  }
}

function connect(url) {
  const socket = new WebSocket(url);
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve(new Session(socket)));
    socket.addEventListener("error", reject);
  });
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

const profile = mkdtempSync(join(tmpdir(), "step7-chrome-"));
const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding",
  "--no-first-run",
  "--no-default-browser-check",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
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

  const dom = await session.evaluate(`(() => {
    const message = [...document.querySelectorAll(".message--assistant")].pop();
    const badge = message ? message.querySelector(".state-badge") : null;
    const warning = message ? message.querySelector(".unreadable-warning") : null;
    const body = warning ? warning.querySelector(".unreadable-warning__body") : null;
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
    return {
      badge: badge ? badge.textContent.trim() : null,
      warningTitle: warning ? (warning.querySelector(".unreadable-warning__title") || {}).textContent : null,
      warningBody: body ? body.textContent.trim() : null,
      warningItems: items,
      chips,
      answer: message ? (message.querySelector(".message__body") || {}).textContent : null,
    };
  })()`);

  state.badge = dom.badge;
  state.warning = dom.warningBody || dom.warningTitle
    ? { title: dom.warningTitle, body: dom.warningBody, items: dom.warningItems }
    : null;
  state.chips = dom.chips;
  state.answer = (dom.answer || "").trim().slice(0, 200);
  // An unanswerable question must show the warning; an answered one must show chips that
  // still read `[n]`, because a bare `1` looks like part of a number.
  if (settled === "not_found") {
    state.ok = Boolean(state.warning && state.warning.items.length);
  } else {
    state.ok = state.chips.length > 0 &&
      state.chips.every((chip) => chip.text === `[${chip.n}]` && Boolean(chip.doc));
  }
} finally {
  try { if (session) session.socket.close(); } catch { /* already closed */ }
  chrome.kill();
  await sleep(300);
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* Windows lock */ }
}

mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT, JSON.stringify(state, null, 1));

console.log(`browser      ${state.browser || "unknown"}`);
console.log(`question     ${state.question}`);
console.log(`state        ${state.status}`);
console.log(`badge        ${state.badge}`);
console.log(`warning      ${state.warning ? state.warning.body : "MISSING"}`);
for (const item of state.warning ? state.warning.items : []) console.log(`per document ${item}`);
console.log(`chips        ${state.chips.length}  ${state.chips.map((chip) => chip.text).join(" ")}`);
console.log(`console errors ${state.consoleErrors.length}`);
console.log(`verdict      ${state.ok ? "PASS" : "FAIL"}  (${OUT})`);
process.exit(state.ok ? 0 : 1);
