/* Chat UI. One delegated listener per event type (D-036): no per-element handlers. */
(() => {
  "use strict";

  const STORAGE = "rag-chat-v1";
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
  };

  const state = {
    conversations: [],
    activeId: null,
    streaming: false,
    controller: null,
    autoScroll: true,
  };

  // ------------------------------------------------------------ persistence

  const load = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE) || "{}");
      state.conversations = Array.isArray(saved.conversations) ? saved.conversations : [];
      state.activeId = saved.activeId || null;
      if (saved.theme) document.documentElement.dataset.theme = saved.theme;
      if (saved.collapsed) el.app.classList.add("app--collapsed");
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
    }));
  };

  const makeConversation = () => ({
    id: `c${Date.now()}${Math.floor(Math.random() * 1000)}`,
    title: "New chat",
    messages: [],
  });

  const active = () => state.conversations.find((c) => c.id === state.activeId);

  // ---------------------------------------------------------------- markdown

  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) =>
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

  const markdown = (src) => src.split("```").map((chunk, i) => {
    if (i % 2 === 1) {
      const body = chunk.replace(/^[^\n]*\n/, "").replace(/\n$/, "");
      return `<pre><code>${escapeHtml(body)}</code></pre>`;
    }
    return blocks(chunk);
  }).join("");

  // ------------------------------------------------------------------ render

  const el2 = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  const formatStats = (meta) => {
    if (!meta) return "";
    const bits = [];
    if (meta.tokensPerSecond) bits.push(`${meta.tokensPerSecond.toFixed(1)} tok/s`);
    if (meta.seconds) bits.push(`${meta.seconds.toFixed(1)}s`);
    if (meta.promptTokens) bits.push(`${meta.promptTokens} prompt`);
    return bits.join(" · ");
  };

  const messageNode = (msg, index) => {
    const wrap = el2("article", `message message--${msg.role}`);
    wrap.dataset.index = String(index);

    if (msg.role === "assistant") {
      const meta = el2("div", "message__meta");
      meta.append(el2("span", null, "assistant"));
      if (msg.meta) meta.append(el2("span", null, formatStats(msg.meta)));
      wrap.append(meta);
    }

    const body = el2("div", "message__body");
    if (msg.role === "assistant") {
      body.innerHTML = markdown(msg.content || "");
      linkCitations(body, msg.sources, index);
      if (msg.pending) body.append(el2("span", "cursor"));
      if (!msg.content && msg.pending) {
        const typing = el2("span", "typing");
        for (let i = 0; i < 3; i++) typing.append(el2("span", "typing__dot"));
        body.append(typing);
      }
    } else {
      body.textContent = msg.content;
    }
    wrap.append(body);

    if (msg.error) wrap.append(el2("div", "message__error", msg.error));
    if (msg.role === "assistant" && msg.sources && msg.sources.length) {
      wrap.append(sourcesNode(msg.sources));
    }

    if (msg.role === "assistant" && !msg.pending) {
      const actions = el2("div", "message__actions");
      const copy = el2("button", "message__action", "Copy");
      copy.dataset.action = "copy";
      copy.dataset.index = String(index);
      actions.append(copy);
      if (index === active().messages.length - 1) {
        const again = el2("button", "message__action", "Regenerate");
        again.dataset.action = "regenerate";
        actions.append(again);
      }
      wrap.append(actions);
    }
    return wrap;
  };

  const sourcesNode = (sources) => {
    const wrap = el2("div", "sources");
    wrap.append(el2("span", "sources__label", "Sources"));
    for (const s of sources) {
      const chip = el2("button", "source");
      chip.dataset.action = "open-source";
      chip.dataset.doc = s.doc;
      chip.dataset.page = String(s.page);
      chip.title = s.snippet || "";
      chip.append(el2("span", "source__n", s.key || String(s.n)));
      chip.append(el2("span", "source__label", `${s.label} · p${s.page}${s.ocr ? " · OCR" : ""}`));
      wrap.append(chip);
    }
    return wrap;
  };

  /* Turn [1] markers into buttons, skipping code blocks. */
  const linkCitations = (container, sources, index) => {
    if (!sources || !sources.length) return;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement && node.parentElement.closest("pre, code")) continue;
            if (/\[[A-H]\]/.test(node.nodeValue)) nodes.push(node);
    }
    for (const node of nodes) {
      const text = node.nodeValue;
      const frag = document.createDocumentFragment();
      let last = 0;
      for (const match of text.matchAll(/\[([A-H])\]/g)) {
        frag.append(document.createTextNode(text.slice(last, match.index)));
        const btn = el2("button", "cite", match[1]);
        btn.dataset.action = "open-source";
        btn.dataset.index = String(index);
        btn.dataset.key = match[1];
        btn.title = "Open the cited page";
        frag.append(btn);
        last = match.index + match[0].length;
      }
      frag.append(document.createTextNode(text.slice(last)));
      node.replaceWith(frag);
    }
  };

  /* A real anchor beats window.open here: browsers treat it as a normal
     navigation, so no popup blocker gets in the way. */
  const openSource = (doc, page) => {
    if (!doc) return;
    const link = document.createElement("a");
    link.href = `/pdf/${encodeURIComponent(doc)}#page=${page}`;
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
      lines.push(`## ${msg.role === "user" ? "You" : "Assistant"}`, "", msg.content, "");
      if (msg.sources && msg.sources.length) {
        lines.push("**Sources**", "");
        for (const s of msg.sources) {
          lines.push(`- [${s.key || s.n}] ${s.label}, page ${s.page} (${s.doc}) — ${s.snippet}`);
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
    convo.messages.forEach((msg, i) => el.thread.append(messageNode(msg, i)));
    el.thread.append(el2("div", "chat__spacer"));
  };

  const renderSidebar = () => {
    el.list.replaceChildren();
    if (!state.conversations.length) {
      el.list.append(el2("div", "sidebar__empty", "No conversations yet."));
      return;
    }
    for (const convo of state.conversations) {
      const item = el2("div", `chat-item${convo.id === state.activeId ? " chat-item--active" : ""}`);
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

  const atBottom = () => el.scroll.scrollHeight - el.scroll.scrollTop - el.scroll.clientHeight < 80;

  const scrollDown = () => {
    if (state.autoScroll) el.scroll.scrollTop = el.scroll.scrollHeight;
  };

  // ---------------------------------------------------------------- streaming

  const setStreaming = (flag) => {
    state.streaming = flag;
    el.send.classList.toggle("composer__send--stop", flag);
    el.send.setAttribute("aria-label", flag ? "Stop" : "Send");
    el.send.innerHTML = flag ? "&#9632;" : "&#8593;";
    el.send.disabled = false;
    el.status.textContent = flag ? "generating…" : "";
  };

  const chat = async (convo, assistantMsg) => {
    state.controller = new AbortController();
    setStreaming(true);
    const started = performance.now();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: convo.messages
            .filter((m) => !m.error)
            .map((m) => ({ role: m.role, content: m.content })),
          temperature: 0,
        }),
        signal: state.controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let firstToken = null;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          let chunk;
          try { chunk = JSON.parse(line); } catch { continue; }
          if (chunk.error) throw new Error(chunk.error);

          if (chunk.message && chunk.message.content) {
            if (firstToken === null) firstToken = performance.now();
            assistantMsg.content += chunk.message.content;
            assistantMsg.pending = true;
            paintAssistant(convo, assistantMsg);
            scrollDown();
          }
          if (chunk.done) {
            const genSeconds = (chunk.eval_duration || 0) / 1e9;
            assistantMsg.meta = {
              seconds: (performance.now() - started) / 1000,
              firstTokenMs: firstToken ? firstToken - started : null,
              tokensPerSecond: genSeconds > 0 ? (chunk.eval_count || 0) / genSeconds : null,
              promptTokens: chunk.prompt_eval_count || null,
            };
            assistantMsg.sources = Array.isArray(chunk.sources) ? chunk.sources : [];
          }
        }
      }
      assistantMsg.pending = false;
      if (!assistantMsg.content.trim()) {
        assistantMsg.error = "The model returned an empty answer.";
      }
    } catch (err) {
      assistantMsg.pending = false;
      if (err.name === "AbortError") {
        assistantMsg.content += assistantMsg.content ? "\n\n_(stopped)_" : "_(stopped)_";
      } else {
        assistantMsg.error = String(err.message || err);
      }
    } finally {
      setStreaming(false);
      state.controller = null;
      save();
      renderThread();
      scrollDown();
    }
  };

  const paintAssistant = (convo, msg) => {
    const index = convo.messages.indexOf(msg);
    const node = el.thread.querySelector(`.message[data-index="${index}"] .message__body`);
    if (!node) return;
    node.innerHTML = markdown(msg.content || "");
    if (msg.pending) node.append(el2("span", "cursor"));
  };

  // -------------------------------------------------------------------- send

  const send = (text) => {
    const content = (text != null ? text : el.input.value).trim();
    if (!content || state.streaming) return;

    const convo = active();
    if (!convo.messages.length) convo.title = content.slice(0, 46) + (content.length > 46 ? "…" : "");
    convo.messages.push({ role: "user", content });
    const assistantMsg = { role: "assistant", content: "", pending: true, meta: null, error: null };
    convo.messages.push(assistantMsg);

    el.input.value = "";
    el.input.style.height = "auto";
    renderSidebar();
    renderThread();
    scrollDown();
    save();
    chat(convo, assistantMsg);
  };

  const regenerate = () => {
    const convo = active();
    if (state.streaming) return;
    while (convo.messages.length && convo.messages[convo.messages.length - 1].role === "assistant") {
      convo.messages.pop();
    }
    if (!convo.messages.length) return;
    const assistantMsg = { role: "assistant", content: "", pending: true, meta: null, error: null };
    convo.messages.push(assistantMsg);
    renderThread();
    chat(convo, assistantMsg);
  };

  // -------------------------------------------------------------- delegation

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;

    if (action === "new-chat") {
      const convo = makeConversation();
      state.conversations.unshift(convo);
      state.activeId = convo.id;
      renderSidebar(); renderThread(); save();
      el.input.focus();
    } else if (action === "toggle-sidebar") {
      el.app.classList.toggle("app--collapsed");
      save();
    } else if (action === "toggle-theme") {
      const dark = document.documentElement.dataset.theme !== "dark";
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      save();
    } else if (action === "suggest") {
      send(target.textContent);
    } else if (action === "open-chat") {
      state.activeId = target.dataset.id;
      renderSidebar(); renderThread(); save();
    } else if (action === "delete-chat") {
      event.stopPropagation();
      state.conversations = state.conversations.filter((c) => c.id !== target.dataset.id);
      if (!state.conversations.length) state.conversations.push(makeConversation());
      if (!state.conversations.some((c) => c.id === state.activeId)) {
        state.activeId = state.conversations[0].id;
      }
      renderSidebar(); renderThread(); save();
    } else if (action === "copy") {
      const msg = active().messages[Number(target.dataset.index)];
      navigator.clipboard.writeText(msg.content).then(() => {
        const old = target.textContent;
        target.textContent = "Copied";
        setTimeout(() => { target.textContent = old; }, 1200);
      });
    } else if (action === "regenerate") {
      regenerate();
    } else if (action === "export-chat") {
      exportChat();
    } else if (action === "open-source") {
      if (target.dataset.doc) {
        openSource(target.dataset.doc, target.dataset.page);
      } else {
        const msg = active().messages[Number(target.dataset.index)];
        const src = (msg.sources || []).find(
          (s) => (s.key || String(s.n)) === target.dataset.key
        );
        if (src) openSource(src.doc, src.page);
      }
    }
  });

  el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.streaming) {
      if (state.controller) state.controller.abort();
      return;
    }
    send();
  });

  el.input.addEventListener("input", () => {
    el.input.style.height = "auto";
    el.input.style.height = `${Math.min(el.input.scrollHeight, 200)}px`;
    el.send.disabled = !el.input.value.trim() && !state.streaming;
  });

  el.input.addEventListener("keydown", (event) => {
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
      if (!health.ok) {
        el.status.textContent = health.error || "model not installed";
      }
    } catch {
      el.status.textContent = "server offline";
    }
  };

  boot();
})();
