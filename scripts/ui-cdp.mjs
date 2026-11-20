// Shared Chrome DevTools plumbing for the UI checks (Step 7, Step 9).
//
// Two checks drive the same headless Chrome over the same protocol: the step-7 check
// (`ui-browser-check.mjs`, one question, warning + viewer) and the starter check
// (`ui-starters-check.mjs`, every empty-state card and every citation chip). This module
// is the one copy of the connection, the evaluate retry and the viewer state probe, so
// adding a third check does not mean a third copy.
//
// Usage:
//   import { connect, launchArgs, waitForJson, sleep, waitForViewer } from "./ui-cdp.mjs";

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

export const CHROME = process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

export async function waitForJson(url, tries = 100) {
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

/** A fresh headless profile, so no saved state leaks into a check. */
export function freshProfile(prefix) {
  const profile = mkdtempSync(join(tmpdir(), prefix));
  return {
    dir: profile,
    args: [
      "--headless=new",
      "--disable-gpu",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "--no-first-run",
      "--no-default-browser-check",
      `--user-data-dir=${profile}`,
    ],
  };
}

export function dropProfile(dir) {
  try { rmSync(dir, { recursive: true, force: true }); } catch { /* Windows lock */ }
}

export class Session {
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

export function connect(url) {
  const socket = new WebSocket(url);
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve(new Session(socket)));
    socket.addEventListener("error", reject);
  });
}

/** The citation viewer's visible state, or null when it is closed. */
export const VIEWER_STATE = `(() => {
  const root = document.querySelector(".cite-viewer");
  if (!root || root.hidden) return null;
  const canvas = root.querySelector(".cite-viewer__canvas");
  const hits = [...root.querySelectorAll(".cite-viewer__hit")];
  return {
    title: (root.querySelector(".cite-viewer__title") || {}).textContent || "",
    meta: (root.querySelector(".cite-viewer__meta") || {}).textContent || "",
    page: (root.querySelector(".cite-viewer__page") || {}).value || "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    hits: hits.length,
    hitText: ((root.querySelector(".cite-viewer__marks") || {}).dataset || {}).quote || "",
    hitBox: hits.length
      ? { w: Math.round(hits[0].getBoundingClientRect().width),
          h: Math.round(hits[0].getBoundingClientRect().height) }
      : null,
    note: ((root.querySelector(".cite-viewer__note") || {}).textContent || "").slice(0, 120),
  };
})()`;

export async function waitForViewer(session, test, tries = 80) {
  for (let i = 0; i < tries; i += 1) {
    await sleep(250);
    const seen = await session.evaluate(VIEWER_STATE);
    if (seen && test(seen)) return seen;
  }
  return null;
}

export const clickViewer = (session, action) => session.evaluate(
  `(() => { const b = document.querySelector('.cite-viewer [data-action="${action}"]');
            if (!b || b.disabled) return false;
            b.click();
            return true; })()`);
