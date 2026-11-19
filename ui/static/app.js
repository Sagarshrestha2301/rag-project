/* Step 7 chat client. One delegated listener per event type (D-036): five listeners in
   total for the whole app, all at the bottom of this file. Nothing here decides an
   answer: the server streams events from the measured pipeline (D-061). */
(() => {
  "use strict";

  const STORAGE = "rag-chat-v2";
  const STATES = {
    streaming: { glyph: "…", label: "streaming" },
    verified: { glyph: "✓", label: "verified" },
    unverified: { glyph: "!", label: "unverified — retracted" },
    not_found: { glyph: "∅", label: "not found" },
    error: { glyph: "×", label: "error" },
    greeting: { glyph: "·", label: "no lookup" },
  };

  const el = {
    app: document.getElementById("app"),
    thread: document.getElementById("thread"),
    scroll: document.getElementById("chat-scroll"),
    list: document.getElementById("conversation-list"),
    title: document.getElementById("chat-title"),
    status: document.getElementById("chat-status"),
    form: document.getElementById("composer-form"),
    input: document.getElementById("composer-input"),
    send: document.getElementById("send-button"),
    empty: document.getElementById("empty-state"),
    model: document.getElementById("model-badge"),
    evidence: document.getElementById("evidence-body"),
    corpusLine: document.getElementById("corpus-line"),
  };

  const state = {
    conversations: [],
    activeId: null,
    streaming: false,
    controller: null,
    autoScroll: true,
    evidenceIndex: null,
    tab: "sources",
  };

  // ------------------------------------------------------------ persistence

  const makeConversation = () => ({
    id: `c${Date.now()}${Math.floor(Math.random() * 1000)}`,
    title: "New chat",
    messages: [],
  });

  const load = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE) || "{}");
      state.conversations = Array.isArray(saved.conversations) ? saved.conversations : [];
      state.activeId = saved.activeId || null;
      if (saved.theme) document.documentElement.dataset.theme = saved.theme;
      if (saved.collapsed) el.app.classList.add("app--collapsed");
      if (saved.evidenceHidden) el.app.classList.add("app--evidence-hidden");
      if (typeof saved.evidenceIndex === "number") state.evidenceIndex = saved.evidenceIndex;
      if (saved.tab) state.tab = saved.tab;
    } catch {
      state.conversations = [];
    }
    if (!state.conversations.length) state.conversations.push(makeConversation());
    if (!state.conversations.some((c) => c.id === state.activeId)) {
      state.activeId = state.conversations[0].id;
    }
  };

  const save = () => {
    localStorage.setItem(STORAGE, JSON.stringify({
      conversations: state.conversations,
      activeId: state.activeId,
      theme: document.documentElement.dataset.theme,
      collapsed: el.app.classList.contains("app--collapsed"),
      evidenceHidden: el.app.classList.contains("app--evidence-hidden"),
      evidenceIndex: state.evidenceIndex,
      tab: state.tab,
    }));
  };

  const active = () => state.conversations.find((c) => c.id === state.activeId);

  // ---------------------------------------------------------------- markdown

  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const inline = (t) => t
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  const blocks = (text) => {
    const out = [];
    let list = [];
    let para = [];
    const flushPara = () => {
      if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; }
    };
    const flushList = () => {
      if (list.length) {
        out.push(`<ul>${list.map((li) => `<li>${inline(li)}</li>`).join("")}</ul>`);
        list = [];
      }
    };
    for (const raw of escapeHtml(text).split("\n")) {
      const line = raw.trim();
      if (!line) { flushPara(); flushList(); continue; }
      const heading = line.match(/^(#{1,3})\s+(.*)$/);
      if (heading) {
        flushPara(); flushList();
        const level = heading[1].length + 1;
        out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        continue;
      }
      if (/^[-*•]\s+/.test(line)) {
        flushPara();
        list.push(line.replace(/^[-*•]\s+/, ""));
        continue;
      }
      flushList();
      para.push(line);
    }
    flushPara(); flushList();
    return out.join("");
  };

  const markdown = (src) => String(src || "").split("```").map((chunk, i) => {
    if (i % 2 === 1) {
      const body = chunk.replace(/^[^\n]*\n/, "").replace(/\n$/, "");
      return `<pre><code>${escapeHtml(body)}</code></pre>`;
    }
    return blocks(chunk);
  }).join("");

  // ------------------------------------------------------------ shared nodes

  const el2 = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  const formatStats = (meta, payload) => {
    const bits = [];
    if (meta && meta.seconds) bits.push(`${meta.seconds.toFixed(1)} s`);
    if (payload && payload.tokens && payload.tokens.answer) {
      const seconds = (payload.timings_ms.model_total || 0) / 1000;
      if (seconds > 0) bits.push(`${(payload.tokens.answer / seconds).toFixed(1)} tok/s`);
    }
    if (payload && payload.tokens && payload.tokens.prompt) {
      bits.push(`${payload.tokens.prompt} prompt`);
    }
    if (payload && payload.cached) bits.push("cached");
    return bits.join(" · ");
  };

  const stateBadge = (name, payload) => {
    const info = STATES[name] || { glyph: "·", label: name || "unknown" };
    let label = info.label;
    if (name === "verified" && payload) {
      const quotes = (payload.verification && payload.verification.verified_quotes) || 0;
      label = `verified · ${quotes} quote${quotes === 1 ? "" : "s"}`;
    }
    const badge = el2("span", `state-badge state-badge--${name}`, `${info.glyph} ${label}`);
    badge.dataset.role = "state";
    return badge;
  };

  // The marker keeps its brackets on screen: a bare `1` after "540 mm" reads like part of
  // the number, and three sentences citing one page then look like "1 1 1".
  const chipNode = (n, source, quote, disabled) => {
    const chip = el2("button", "cite", `[${n}]`);
    chip.dataset.action = "open-source";
    chip.dataset.n = String(n);
    if (source) {
      chip.dataset.doc = source.doc;
      // Everything the citation viewer needs comes with the payload: the page, the text
      // to highlight, and the work's name for its title bar. The highlighted text is the
      // quote the verifier checked against the page - more precise than the whole
      // retrieved passage - and the passage is the fallback.
      chip.dataset.page = String(source.page || 1);
      chip.dataset.text = quote || source.snippet || "";
      chip.dataset.title = source.reference || source.label || source.doc || "";
    }
    chip.title = disabled ? "Unverified: the citation is not trusted" : "Open the cited page";
    if (disabled) chip.classList.add("cite--disabled");
    return chip;
  };

  /* The citation line the prompt asks for — `[1] <file>, p. <n>: "<quote>"` — is a
     reference, not a claim marker: its number is already a source in the evidence rail,
     so turning it into a chip only repeats the same marker after the last sentence. */
  const isReferenceLine = (node) => {
    const block = node.parentElement && node.parentElement.closest("p, li, h2, h3, h4");
    if (!block) return false;
    const text = block.textContent.trim();
    const reference = /^\[\d{1,2}\]\s+\S/.test(text) && /,\s*p\.\s*\d+\s*:/i.test(text);
    if (reference) block.classList.add("message__ref");
    return reference;
  };

  /* Turn [1] markers into chips. Numbers, not letters: prompt s6-2 numbers passages. */
  const linkCitations = (container, sources, citations, disabled) => {
    const byN = new Map((sources || []).map((s) => [String(s.n), s]));
    const quoteByN = new Map((citations || [])
      .filter((c) => c && c.quote)
      .map((c) => [String(c.n), c.quote]));
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement && node.parentElement.closest("pre, code")) continue;
      if (!/\[\d{1,2}\]/.test(node.nodeValue)) continue;
      if (isReferenceLine(node)) continue;
      nodes.push(node);
    }
    for (const node of nodes) {
      const text = node.nodeValue;
      const frag = document.createDocumentFragment();
      let last = 0;
      for (const match of text.matchAll(/\[(\d{1,2})\]/g)) {
        frag.append(document.createTextNode(text.slice(last, match.index)));
        frag.append(chipNode(match[1], byN.get(match[1]), quoteByN.get(match[1]), disabled));
        last = match.index + match[0].length;
      }
      frag.append(document.createTextNode(text.slice(last)));
      node.replaceWith(frag);
    }
  };

  const unreadableNode = (payload) => {
    const data = payload && payload.unreadable;
    if (!data || !data.corpus) return null;
    const corpus = data.corpus;
    const box = el2("div", "unreadable-warning");
    box.append(el2("p", "unreadable-warning__title", "Some pages cannot be read"));
    // Two different sets of pages, said as two facts: the pages that stayed empty after
    // OCR, and the pages OCR did read. One clause joined them and read as if the 19 were
    // part of the 86.
    box.append(el2("p", "unreadable-warning__body",
      `${corpus.unreadable_pages} of ${corpus.pages} pages, in ` +
      `${corpus.documents_with_unreadable} of ${corpus.documents} documents, still have no ` +
      `readable text after OCR. ${corpus.ocr_pages} pages were read by OCR. ` +
      `The answer may simply not be on a readable page.`));
    const list = (data.top_documents || []);
    if (list.length) {
      const ul = el2("ul", "unreadable-warning__list");
      for (const doc of list) {
        ul.append(el2("li", null,
          `${doc.label || doc.doc} has ${doc.count} unreadable page` +
          `${doc.count === 1 ? "" : "s"}: ${doc.pages.join(", ")}`));
      }
      box.append(ul);
    }
    return box;
  };

  const actionsNode = (msg, index, isLast) => {
    const actions = el2("div", "message__actions");
    if (msg.state === "error") {
      const retry = el2("button", "message__action", "Retry");
      retry.dataset.action = "retry";
      actions.append(retry);
      return actions;
    }
    if (msg.content) {
      const copy = el2("button", "message__action",
        msg.state === "unverified" ? "Copy anyway" : "Copy");
      copy.dataset.action = "copy";
      copy.dataset.index = String(index);
      actions.append(copy);
    }
    if (isLast) {
      const again = el2("button", "message__action", "Regenerate");
      again.dataset.action = "regenerate";
      actions.append(again);
    }
    return actions;
  };

  const messageNode = (msg, index, isLast) => {
    const wrap = el2("article", `message message--${msg.role}`);
    wrap.dataset.index = String(index);
    if (msg.state) wrap.dataset.state = msg.state;
    if (msg.state === "unverified") wrap.classList.add("message--unverified");

    if (msg.role === "assistant") {
      const meta = el2("div", "message__meta");
      meta.append(el2("span", null, (msg.meta && msg.meta.model) || "assistant"));
      const stats = formatStats(msg.meta, msg.payload);
      if (stats) meta.append(el2("span", null, stats));
      if (msg.state) meta.append(stateBadge(msg.state, msg.payload));
      wrap.append(meta);
    }

    const body = el2("div", "message__body");
    if (msg.role === "user") {
      body.textContent = msg.content;
    } else {
      body.innerHTML = markdown(msg.content || "");
      const sources = (msg.payload && msg.payload.sources) || [];
      const citations = (msg.payload && msg.payload.verification &&
        msg.payload.verification.citations) || [];
      linkCitations(body, sources, citations, msg.state === "unverified");
      if (msg.state === "streaming") {
        if (!msg.content) {
          const typing = el2("span", "typing");
          for (let i = 0; i < 3; i++) typing.append(el2("span", "typing__dot"));
          body.append(typing);
        } else {
          body.append(el2("span", "cursor"));
        }
      }
    }
    wrap.append(body);

    if (msg.state === "unverified" && msg.payload) {
      const problems = (msg.payload.verification && msg.payload.verification.problems) || [];
      wrap.append(el2("p", "message__retraction",
        `Retracted: ${problems[0] || "the quotations could not be verified"}`));
      if (problems.length > 1) {
        const list = el2("ul", "message__problems");
        for (const problem of problems.slice(1)) list.append(el2("li", null, problem));
        wrap.append(list);
      }
    }

    if (msg.state === "not_found") {
      const warning = unreadableNode(msg.payload);
      if (warning) wrap.append(warning);
    }

    if (msg.error) wrap.append(el2("div", "message__error", msg.error));

    if (msg.role === "assistant" && msg.state !== "streaming") {
      wrap.append(actionsNode(msg, index, isLast));
    }
    return wrap;
  };

  // ------------------------------------------------------------- evidence rail

  const sourceEntry = (source) => {
    const item = el2("button", "source");
    item.dataset.action = "open-source";
    item.dataset.doc = source.doc || "";
    item.dataset.page = String(source.page || 1);
    item.dataset.text = source.snippet || "";
    item.dataset.title = source.reference || source.label || source.doc || "";
    // `reference` is the extracted citation; `label`/`doc` are only a fallback for a
    // document whose page 1 has no readable header.
    const head = el2("div", "source__head");
    head.append(el2("span", "source__n", `[${source.n}]`));
    head.append(el2("span", "source__label",
      source.reference || source.label || source.doc));
    head.append(el2("span", "source__score",
      typeof source.score === "number" ? source.score.toFixed(2) : "—"));
    item.append(head);
    const meta = el2("div", "source__meta");
    meta.append(el2("span", "source__page",
      `p${source.page}${source.ocr ? " · OCR" : ""}`));
    if (source.doc) {
      const file = el2("span", "source__file", source.doc);
      file.title = source.doc;
      meta.append(file);
    }
    item.append(meta);
    if (source.snippet) item.append(el2("p", "source__quote", source.snippet));
    return item;
  };

  const renderEvidence = () => {
    el.evidence.replaceChildren();
    const convo = active();
    const index = state.evidenceIndex;
    const msg = convo && convo.messages[index];
    const payload = msg && msg.payload;

    if (!payload) {
      el.evidence.append(el2("p", "evidence__empty",
        msg && msg.state === "streaming"
          ? "Waiting for the pipeline to finish…"
          : "Answers put their sources and their debug record here."));
      return;
    }

    if (state.tab === "debug") {
      const bar = el2("div", "debug__bar");
      const copy = el2("button", "debug__copy", "Copy JSON");
      copy.dataset.action = "copy-debug";
      copy.dataset.index = String(index);
      bar.append(copy);
      bar.append(el2("span", "debug__note", `debug_version ${payload.debug_version}`));
      el.evidence.append(bar);
      const pre = el2("pre", "debug__json", JSON.stringify(payload, null, 2));
      el.evidence.append(pre);
      return;
    }

    const sources = payload.sources || [];
    if (!sources.length) {
      el.evidence.append(el2("p", "evidence__empty",
        payload.status === "greeting"
          ? "A greeting does not search the corpus."
          : "No page was offered for this answer."));
      return;
    }
    for (const source of sources) el.evidence.append(sourceEntry(source));
  };

  const renderThread = () => {
    const convo = active();
    el.thread.replaceChildren();
    el.title.textContent = convo.title;

    if (!convo.messages.length) {
      const empty = el.empty.cloneNode(true);
      empty.id = "empty-state";
      el.thread.append(empty);
      return;
    }
    convo.messages.forEach((msg, i) =>
      el.thread.append(messageNode(msg, i, i === convo.messages.length - 1)));
    el.thread.append(el2("div", "chat__spacer"));
    renderEvidence();
  };

  const renderSidebar = () => {
    el.list.replaceChildren();
    if (!state.conversations.length) {
      el.list.append(el2("div", "sidebar__empty", "No conversations yet."));
      return;
    }
    for (const convo of state.conversations) {
      const item = el2("div",
        `chat-item${convo.id === state.activeId ? " chat-item--active" : ""}`);
      item.dataset.action = "open-chat";
      item.dataset.id = convo.id;
      item.append(el2("span", "chat-item__title", convo.title));
      const del = el2("button", "chat-item__delete", "×");
      del.dataset.action = "delete-chat";
      del.dataset.id = convo.id;
      del.title = "Delete conversation";
      item.append(del);
      el.list.append(item);
    }
  };

  const atBottom = () =>
    el.scroll.scrollHeight - el.scroll.scrollTop - el.scroll.clientHeight < 80;

  const scrollDown = () => {
    if (state.autoScroll) el.scroll.scrollTop = el.scroll.scrollHeight;
  };

  const showEvidence = (index) => {
    state.evidenceIndex = index;
    el.app.classList.remove("app--evidence-hidden");
    renderEvidence();
    save();
  };

  // ---------------------------------------------------------------- streaming

  const setStreaming = (flag) => {
    state.streaming = flag;
    el.send.classList.toggle("composer__send--stop", flag);
    el.send.setAttribute("aria-label", flag ? "Stop" : "Send");
    el.send.innerHTML = flag ? "&#9632;" : "&#8593;";
    el.send.disabled = false;
    el.status.textContent = flag ? "searching and generating…" : "";
  };

  const paintAssistant = (index, msg) => {
    const node = el.thread.querySelector(`.message[data-index="${index}"]`);
    if (!node) return;
    const fresh = messageNode(msg, index, true);
    node.replaceWith(fresh);
  };

  const applyDone = (msg, payload) => {
    msg.payload = payload;
    msg.content = payload.answer || msg.content;
    msg.state = payload.status === "greeting" ? "greeting" : payload.status;
    msg.error = null;
    msg.meta = Object.assign(msg.meta || {}, {
      model: payload.model && payload.model.name,
      seconds: (payload.timings_ms && payload.timings_ms.total) / 1000,
    });
  };

  const postChat = async (convo, msg) => {
    state.controller = new AbortController();
    setStreaming(true);
    const started = performance.now();
    const index = convo.messages.indexOf(msg);
    let firstToken = null;

    try {
      const payload = {
        messages: convo.messages
          .filter((m) => !m.error && m !== msg)
          .map((m) => ({ role: m.role, content: m.content })),
        temperature: 0,
      };
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: state.controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          let event;
          try { event = JSON.parse(line); } catch { continue; }

          if (event.event === "token") {
            if (firstToken === null) {
              firstToken = performance.now();
              msg.state = "streaming";
            }
            msg.content += event.text;
            paintAssistant(index, msg);
            scrollDown();
          } else if (event.event === "done") {
            applyDone(msg, event.payload);
          } else if (event.event === "error") {
            throw new Error(event.message || "the server reported an error");
          }
        }
      }

      if (!msg.state || msg.state === "streaming") {
        msg.state = msg.content.trim() ? "verified" : "error";
        if (!msg.content.trim()) msg.error = "The pipeline returned an empty answer.";
      }
      msg.meta = Object.assign(msg.meta || {}, {
        seconds: (performance.now() - started) / 1000,
        firstTokenMs: firstToken ? firstToken - started : null,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        msg.state = "error";
        msg.error = "Stopped. The model may still be finishing in the background.";
      } else {
        msg.state = "error";
        msg.error = String(err.message || err);
      }
    } finally {
      setStreaming(false);
      state.controller = null;
      renderThread();
      showEvidence(index);
      scrollDown();
      save();
    }
  };

  // -------------------------------------------------------------------- send

  const send = (text) => {
    const content = (text != null ? text : el.input.value).trim();
    if (!content || state.streaming) return;

    const convo = active();
    if (!convo.messages.length) {
      convo.title = content.slice(0, 46) + (content.length > 46 ? "…" : "");
    }
    convo.messages.push({ role: "user", content });
    const msg = { role: "assistant", content: "", state: "streaming", payload: null,
      meta: null, error: null };
    convo.messages.push(msg);

    el.input.value = "";
    el.input.style.height = "auto";
    state.evidenceIndex = convo.messages.length - 1;
    state.tab = "sources";
    renderSidebar();
    renderThread();
    scrollDown();
    save();
    postChat(convo, msg);
  };

  const regenerate = () => {
    const convo = active();
    if (state.streaming) return;
    while (convo.messages.length && convo.messages[convo.messages.length - 1].role === "assistant") {
      convo.messages.pop();
    }
    if (!convo.messages.length) return;
    const msg = { role: "assistant", content: "", state: "streaming", payload: null,
      meta: null, error: null };
    convo.messages.push(msg);
    state.evidenceIndex = convo.messages.length - 1;
    renderThread();
    postChat(convo, msg);
  };

  // A citation opens the cited page in the viewer, with the quoted passage highlighted.
  // The tab is the fallback: it is what the UI did before the viewer existed, and it is
  // still the way out if pdf.js cannot render the file.
  const openSource = (doc, page, text, title) => {
    if (!doc) return;
    if (window.CitationViewer && window.CitationViewer.open({
      doc, page: Number(page) || 1, text: text || "", title: title || doc,
    })) return;
    const link = document.createElement("a");
    link.href = `/pdf/${encodeURIComponent(doc)}#page=${page || 1}`;
    link.target = "_blank";
    link.rel = "noopener";
    document.body.append(link);
    link.click();
    link.remove();
  };

  const exportChat = () => {
    const convo = active();
    const lines = [`# ${convo.title}`, "", `_Exported ${new Date().toLocaleString()}_`, ""];
    for (const msg of convo.messages) {
      if (msg.role === "assistant" && msg.state === "streaming") continue;
      lines.push(`## ${msg.role === "user" ? "You" : "Assistant"}`, "");
      if (msg.state) lines.push(`_${STATES[msg.state] ? STATES[msg.state].label : msg.state}_`, "");
      lines.push(msg.content, "");
      if (msg.error) lines.push(`**Error:** ${msg.error}`, "");
      const sources = (msg.payload && msg.payload.sources) || [];
      if (sources.length) {
        lines.push("**Sources**", "");
        for (const s of sources) {
          lines.push(`- [${s.n}] ${s.label}, page ${s.page} (${s.doc}) — score ` +
            `${typeof s.score === "number" ? s.score.toFixed(2) : "—"}`);
        }
        lines.push("");
      }
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${(convo.title || "chat").replace(/[^\w\- ]+/g, "").slice(0, 40) || "chat"}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const copyText = (text, button) => {
    navigator.clipboard.writeText(text).then(() => {
      if (!button) return;
      const old = button.textContent;
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = old; }, 1200);
    });
  };

  // -------------------------------------------------------------- delegation

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) {
      const message = event.target.closest(".message--assistant");
      if (message) showEvidence(Number(message.dataset.index));
      return;
    }
    const action = target.dataset.action;

    if (action === "new-chat") {
      const convo = makeConversation();
      state.conversations.unshift(convo);
      state.activeId = convo.id;
      state.evidenceIndex = null;
      renderSidebar(); renderThread(); save();
      el.input.focus();
    } else if (action === "toggle-sidebar") {
      el.app.classList.toggle("app--collapsed");
      save();
    } else if (action === "toggle-evidence") {
      el.app.classList.toggle("app--evidence-hidden");
      if (!el.app.classList.contains("app--evidence-hidden")) renderEvidence();
      save();
    } else if (action === "show-tab") {
      state.tab = target.dataset.tab;
      for (const tab of el.app.querySelectorAll(".evidence__tab")) {
        tab.classList.toggle("evidence__tab--active", tab.dataset.tab === state.tab);
      }
      renderEvidence();
      save();
    } else if (action === "toggle-theme") {
      const dark = document.documentElement.dataset.theme !== "dark";
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      save();
    } else if (action === "suggest") {
      send(target.textContent);
    } else if (action === "open-chat") {
      state.activeId = target.dataset.id;
      state.evidenceIndex = null;
      renderSidebar(); renderThread(); save();
    } else if (action === "delete-chat") {
      event.stopPropagation();
      state.conversations = state.conversations.filter((c) => c.id !== target.dataset.id);
      if (!state.conversations.length) state.conversations.push(makeConversation());
      if (!state.conversations.some((c) => c.id === state.activeId)) {
        state.activeId = state.conversations[0].id;
      }
      state.evidenceIndex = null;
      renderSidebar(); renderThread(); save();
    } else if (action === "copy") {
      const msg = active().messages[Number(target.dataset.index)];
      copyText(msg.content, target);
    } else if (action === "copy-debug") {
      const msg = active().messages[Number(target.dataset.index)];
      copyText(JSON.stringify(msg.payload, null, 2), target);
    } else if (action === "regenerate") {
      regenerate();
    } else if (action === "retry") {
      regenerate();
    } else if (action === "export-chat") {
      exportChat();
    } else if (action === "open-source") {
      if (target.dataset.doc) {
        openSource(target.dataset.doc, target.dataset.page, target.dataset.text,
                   target.dataset.title);
        return;
      }
      const msg = active().messages[Number(state.evidenceIndex)];
      const sources = (msg && msg.payload && msg.payload.sources) || [];
      const source = sources.find((s) => String(s.n) === target.dataset.n);
      if (source) {
        openSource(source.doc, source.page, source.snippet,
                   source.reference || source.label);
      }
    }
  });

  document.addEventListener("submit", (event) => {
    if (event.target !== el.form) return;
    event.preventDefault();
    if (state.streaming) {
      if (state.controller) state.controller.abort();
      return;
    }
    send();
  });

  document.addEventListener("input", (event) => {
    if (event.target !== el.input) return;
    el.input.style.height = "auto";
    el.input.style.height = `${Math.min(el.input.scrollHeight, 200)}px`;
    el.send.disabled = !el.input.value.trim() && !state.streaming;
  });

  document.addEventListener("keydown", (event) => {
    if (event.target !== el.input) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      el.form.requestSubmit();
    }
  });

  el.scroll.addEventListener("scroll", () => {
    state.autoScroll = atBottom();
  });

  // -------------------------------------------------------------------- boot

  const boot = async () => {
    load();
    renderSidebar();
    renderThread();
    el.send.disabled = true;
    el.input.focus();
    try {
      const health = await (await fetch("/api/health")).json();
      el.model.textContent = health.model + (health.loaded ? " · loaded" : "");
      // The empty state is a template that `renderThread` clones, so the copy on screen
      // is not the node captured at boot: query the live one, or the update lands in a
      // detached element and the reader keeps reading the placeholder.
      const corpusLine = document.querySelector("#corpus-line");
      if (health.documents && corpusLine) {
        corpusLine.textContent =
          `${health.documents} documents (${health.pages} pages) in data/corpus`;
      }
      if (!health.ok) el.status.textContent = health.error || "model not installed";
    } catch {
      el.status.textContent = "server offline";
    }
  };

  boot();
})();
