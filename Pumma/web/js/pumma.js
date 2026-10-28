/* Pumma - by cyber-kk team (https://github.com/cyber-kk) */
"use strict";

const PM = (() => {
  // ------------------------------------------------------------------ state
  const LS_CONV = "pumma.convs.v1";
  const LS_CFG = "pumma.cfg.v1";
  const state = {
    convs: load(LS_CONV, {}),       // { id: { title, messages: [{role, content}] } }
    current: null,                  // active conv id
    cfg: load(LS_CFG, { provider: "auto", base_url: "", api_key: "", model: "" }),
    busy: false,
  };

  function load(key, fallback) {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      return v && typeof v === "object" ? v : fallback;
    } catch (e) { return fallback; }
  }
  function saveConv() { localStorage.setItem(LS_CONV, JSON.stringify(state.convs)); }
  function saveCfg() { localStorage.setItem(LS_CFG, JSON.stringify(state.cfg)); }
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  // ------------------------------------------------------------ mini markdown
  function renderMarkdown(src) {
    const parts = String(src).split(/```/);
    let html = "";
    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 1) {
        // fenced code block
        let block = parts[i];
        let lang = "";
        const nl = block.indexOf("\n");
        if (nl > -1) {
          const first = block.slice(0, nl).trim();
          if (/^[\w+#-]{1,16}$/.test(first)) { lang = first.toLowerCase(); block = block.slice(nl + 1); }
        }
        html += codeBlock(block.replace(/\n$/, ""), lang);
      } else {
        html += inlineMd(parts[i]);
      }
    }
    return html;
  }

  function inlineMd(text) {
    let out = esc(text);
    out = out.replace(/^###\s?(.+)$/gm, "<h3>$1</h3>");
    out = out.replace(/`([^`\n]+)`/g, '<span class="inline-code">$1</span>');
    out = out.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>");
    out = out.replace(/(^|\s)\*([^*\n]+)\*(?=\s|$|[.,!?])/g, "$1<i>$2</i>");
    // links [t](url) then bare urls
    out = out.replace(/\[([^\]\n]{1,80})\]\((https?:[^)\s]{1,300})\)/g,
      '<a href="$2" target="_blank" rel="noopener nofollow">$1</a>');
    out = out.replace(/(^|[\s(])(https?:\/\/[^\s<)]{4,200})/g,
      '$1<a href="$2" target="_blank" rel="noopener nofollow">$2</a>');
    // simple lists
    out = out.replace(/(^|\n)((?:[-*]\s.+(?:\n|$))+)/g, (m, p, list) =>
      p + "<ul>" + list.trim().split("\n").map((l) =>
        "<li>" + l.replace(/^\s*[-*]\s*/, "") + "</li>").join("") + "</ul>");
    return out;
  }

  function codeBlock(code, lang) {
    const id = "cb" + Math.random().toString(36).slice(2, 9);
    const isPy = lang === "python" || lang === "py";
    return (
      '<div class="codeblock" data-code-id="' + id + '">' +
      '<div class="code-head"><span>' + esc(lang || "code") + "</span>" +
      '<span class="cb-actions">' +
      (isPy ? runBtn(id) : "") +
      copyBtn(id) +
      "</span></div>" +
      '<pre data-role="code" data-id="' + id + '">' + esc(code) + "</pre>" +
      "</div>"
    );
  }

  function runBtn(id) {
    return '<button class="cb-btn run-btn" data-act="run" data-id="' + id + '">' +
      '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10-6.5z" fill="currentColor"/></svg>Run</button>';
  }
  function copyBtn(id) {
    return '<button class="cb-btn" data-act="copy" data-id="' + id + '">' +
      '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/>' +
      '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" fill="none" stroke="currentColor" stroke-width="2"/></svg>Copy</button>';
  }

  function getCode(id) {
    const el = document.querySelector('pre[data-role="code"][data-id="' + id + '"]');
    return el ? el.textContent : "";
  }

  async function runCode(id, container) {
    const code = getCode(id);
    if (!code.trim()) return;
    const out = document.createElement("div");
    out.className = "code-out busy";
    out.innerHTML = '<span class="out-label">RUNNING...</span>';
    container.querySelector(".codeblock").appendChild(out);
    try {
      const r = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await r.json();
      out.classList.remove("busy");
      let body = "";
      if (data.stdout) body += data.stdout;
      if (data.stderr) body += (body ? "\n" : "") + data.stderr;
      if (data.exit_code === "timeout") body = (body ? body + "\n" : "") + "Stopped: timeout.";
      if (!body) body = data.ok ? "(finished, no output)" : "(no output)";
      if (data.truncated) body += "\n... (output truncated)";
      out.classList.toggle("err", !data.ok);
      out.innerHTML = '<span class="out-label">' +
        (data.ok ? "OUTPUT" : "FAILED (exit " + esc(String(data.exit_code)) + ", " + data.duration_ms + " ms)") +
        "</span>" + esc(body);
    } catch (e) {
      out.classList.remove("busy");
      out.classList.add("err");
      out.innerHTML = '<span class="out-label">ERROR</span>' + esc(String(e.message || e));
    }
  }

  // ----------------------------------------------------------------- events
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) { send(chip.dataset.prompt); return; }
    const act = e.target.closest(".cb-btn");
    if (act) {
      const id = act.dataset.id;
      if (act.dataset.act === "copy") {
        navigator.clipboard && navigator.clipboard.writeText(getCode(id)).then(() => {
          act.innerHTML = act.innerHTML.replace("Copy", "Copied");
          setTimeout(() => { act.innerHTML = copyBtn(id); }, 1200);
        });
      } else if (act.dataset.act === "run") {
        runCode(id, act.closest(".msg-content") || document);
      }
      return;
    }
    const conv = e.target.closest(".conv-item");
    if (conv && conv.dataset.cid) { openConv(conv.dataset.cid); return; }
    const del = e.target.closest(".ci-del");
    if (del && del.dataset.cid) {
      e.stopPropagation();
      delete state.convs[del.dataset.cid];
      if (state.current === del.dataset.cid) state.current = null;
      saveConv(); renderConvList(); renderMessages();
    }
  });

  // ------------------------------------------------------------------ chat
  function currentConv() {
    if (!state.current || !state.convs[state.current]) {
      const id = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      state.convs[id] = { title: "New chat", messages: [] };
      state.current = id;
      saveConv();
    }
    return state.convs[state.current];
  }

  function newChat() {
    state.current = null;
    closeDrawer();
    renderConvList();
    renderMessages();
    $("input").focus();
  }

  function openConv(id) {
    state.current = id;
    closeDrawer();
    renderConvList();
    renderMessages();
  }

  function renderConvList() {
    const wrap = $("conv-list");
    const ids = Object.keys(state.convs).sort((a, b) => {
      const ma = state.convs[a].messages.at(-1)?.t || 0;
      const mb = state.convs[b].messages.at(-1)?.t || 0;
      return mb - ma;
    });
    wrap.innerHTML = ids.map((id) => {
      const c = state.convs[id];
      const active = id === state.current ? " active" : "";
      return '<div class="conv-item' + active + '" data-cid="' + id + '">' +
        '<span class="ci-title">' + esc(c.title || "New chat") + "</span>" +
        '<button class="ci-del" data-cid="' + id + '" aria-label="Delete">' +
        '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-9 0 1 13h8l1-13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        "</button></div>";
    }).join("");
  }

  function renderMessages() {
    const wrap = $("chat-inner-max");
    const conv = state.current ? state.convs[state.current] : null;
    if (!conv || !conv.messages.length) {
      $("welcome").classList.remove("hidden");
      wrap.innerHTML = "";
      return;
    }
    $("welcome").classList.add("hidden");
    wrap.innerHTML = conv.messages.map((m) => bubble(m.role, m.content)).join("");
    $("chat-area").scrollTop = $("chat-area").scrollHeight;
  }

  function bubble(role, content) {
    const avatar = role === "user"
      ? '<div class="avatar">YOU</div>'
      : '<div class="avatar"><svg viewBox="0 0 24 24"><path d="M6 21V3h7a5 5 0 0 1 0 10H6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></div>';
    return '<div class="msg ' + (role === "user" ? "user" : "bot") + '">' + avatar +
      '<div class="bubble"><div class="msg-content">' + renderMarkdown(content) + "</div></div></div>";
  }

  function errorBubble(text) {
    const wrap = $("chat-inner-max");
    wrap.insertAdjacentHTML("beforeend",
      '<div class="msg bot"><div class="avatar">!</div>' +
      '<div class="bubble"><div class="msg-content" style="color:var(--danger)">' + esc(text) + "</div></div></div>");
    $("chat-area").scrollTop = $("chat-area").scrollHeight;
  }

  async function send(text) {
    text = (text || $("input").value || "").trim();
    if (!text || state.busy) return;
    const conv = currentConv();
    $("input").value = ""; autoGrow();
    if (conv.messages.length === 0) {
      conv.title = text.slice(0, 42) + (text.length > 42 ? "..." : "");
      $("welcome").classList.add("hidden");
    }
    conv.messages.push({ role: "user", content: text, t: Date.now() });
    saveConv(); renderConvList();

    const wrap = $("chat-inner-max");
    wrap.insertAdjacentHTML("beforeend", bubble("user", text));
    state.busy = true;
    $("btn-send").disabled = true;
    $("typing").classList.remove("hidden");
    $("chat-area").scrollTop = $("chat-area").scrollHeight;

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: conv.messages.slice(-30).map(({ role, content }) => ({ role, content })),
          config: state.cfg,
        }),
      });
      const data = await r.json();
      $("typing").classList.add("hidden");
      if (data.error) {
        errorBubble("Pumma: " + data.error);
      } else {
        conv.messages.push({ role: "assistant", content: data.reply, t: Date.now() });
        saveConv(); renderConvList();
        wrap.insertAdjacentHTML("beforeend", bubble("assistant", data.reply));
      }
    } catch (e) {
      $("typing").classList.add("hidden");
      errorBubble("Connection to the Pumma server failed. Is server.py still running?");
    }
    state.busy = false;
    $("btn-send").disabled = false;
    $("chat-area").scrollTop = $("chat-area").scrollHeight;
    $("input").focus();
  }

  // ------------------------------------------------------------------ misc
  function autoGrow() {
    const el = $("input");
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }

  function openDrawer() { $("drawer").classList.add("open"); $("drawer-backdrop").classList.add("open"); }
  function closeDrawer() { $("drawer").classList.remove("open"); $("drawer-backdrop").classList.remove("open"); }

  async function refreshProvider() {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      $("provider-dot").textContent = d.provider || "";
      $("active-provider").textContent = d.provider || "";
    } catch (e) { $("provider-dot").textContent = "offline"; }
  }

  function openSettings() {
    $("set-provider").value = state.cfg.provider || "auto";
    $("set-base").value = state.cfg.base_url || "";
    $("set-key").value = state.cfg.api_key || "";
    $("set-model").value = state.cfg.model || "";
    toggleApiFields();
    $("modal-backdrop").classList.remove("hidden");
    $("settings-modal").classList.remove("hidden");
    refreshProvider();
  }
  function closeSettings() {
    $("modal-backdrop").classList.add("hidden");
    $("settings-modal").classList.add("hidden");
  }
  function toggleApiFields() {
    const isApi = $("set-provider").value === "openai";
    ["f-base", "f-key", "f-model"].forEach((id) => $(id).style.display = isApi ? "" : "none");
  }

  function bind() {
    $("btn-menu").onclick = openDrawer;
    $("drawer-close").onclick = closeDrawer;
    $("drawer-backdrop").onclick = closeDrawer;
    $("drawer-new").onclick = newChat;
    $("btn-new").onclick = newChat;
    $("btn-settings").onclick = openSettings;
    $("settings-close").onclick = closeSettings;
    $("modal-backdrop").onclick = closeSettings;
    $("set-provider").onchange = toggleApiFields;
    $("set-save").onclick = () => {
      state.cfg = {
        provider: $("set-provider").value,
        base_url: $("set-base").value.trim(),
        api_key: $("set-key").value.trim(),
        model: $("set-model").value.trim(),
      };
      saveCfg();
      closeSettings();
      refreshProvider();
    };
    $("btn-send").onclick = () => send();
    $("input").addEventListener("input", autoGrow);
    $("input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }

  function boot() {
    bind();
    renderConvList();
    renderMessages();
    refreshProvider();
  }

  document.addEventListener("DOMContentLoaded", boot);

  return { send, newChat };
})();
