#!/usr/bin/env python3
"""Pumma core - identity, engine routing and providers.

Pumma is an AI assistant by the cyber-kk team (https://github.com/cyber-kk),
converted from DeepSeek-Coder technology. The model itself is not shipped in
this repository; Pumma connects to a "brain" you provide:

  1. OpenAI-compatible API  (DeepSeek API, OpenRouter, Ollama, llama.cpp
     server, LM Studio, ... - anything speaking /chat/completions)
  2. Bundled "zai" bridge   (used inside the Z.ai sandbox for live previews)
  3. Pumma Core (offline)   - honest built-in fallback so the app always works

The Pumma identity and personality are applied to every connected brain
through the system prompt below.
"""

import ast
import json
import os
import re
import shutil
import subprocess

TEAM = "cyber-kk"
TEAM_URL = "https://github.com/cyber-kk"

IDENTITY_PROMPT = """You are Pumma, an AI assistant built by the cyber-kk development team (%s).
Your engine is based on DeepSeek-Coder technology, converted and maintained by the cyber-kk team as Pumma.

How you behave:
1. Identity: You always introduce yourself as Pumma. You never say you were built by any other company or team besides cyber-kk.
2. Doer mindset: When the user asks you to do something, you do your best to deliver exactly that. You never end the conversation with a flat "I can't". If a requested approach truly is not possible, you say so in one short sentence and immediately deliver the closest working alternative.
3. Programmer excellence: You are an expert programmer. You prefer complete, runnable code over vague descriptions. Put Python code inside ```python fenced blocks so the user can run it with the Run button.
4. Clarity: You answer in a clear, structured and direct way, without filler.
5. Language: You reply in the same language the user writes in.
""" % TEAM_URL

CHAT_TIMEOUT = 120


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------
def _openai_compat(messages, base_url, api_key, model):
    """Call any OpenAI-compatible /chat/completions endpoint. Returns reply text."""
    import urllib.error
    import urllib.request

    base = base_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    url = base + "/chat/completions"

    payload = {
        "model": model or "pumma",
        "messages": messages,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if not reply:
        raise RuntimeError("Empty response from the backend model.")
    return reply


def _zai_bridge(bridge_path, messages):
    """Call the bundled zai bridge (node + z-ai-web-dev-sdk). Returns reply text."""
    proc = subprocess.run(
        ["node", bridge_path],
        input=json.dumps({"messages": messages}).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=CHAT_TIMEOUT,
        cwd=os.path.dirname(bridge_path),
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    if not out:
        raise RuntimeError("zai bridge failed: %s" % proc.stderr.decode("utf-8", "replace")[:300])
    data = json.loads(out)
    if data.get("error"):
        raise RuntimeError(data["error"][:300])
    reply = data.get("reply") or ""
    if not reply:
        raise RuntimeError("Empty response from the zai bridge.")
    return reply


# --------------------------------------------------------------------------
# Pumma Core (offline engine) - honest fallback, always available
# --------------------------------------------------------------------------
class PummaOffline:
    NAME = "pumma-core-offline"

    _IDENTITY_RE = re.compile(
        r"who\s+are\s+you|your\s+name|what\s+are\s+you|khi\s+haee|esmet|"
        r"تو\s+کی\s+هستی|اسمت\s+چیه|خودت\s+رو\s+معرفی",
        re.I,
    )
    _HELLO_RE = re.compile(r"^\s*(hi|hello|hey|سلام|درود|salam)[\s!.؟?]*$", re.I)
    _THANKS_RE = re.compile(r"thank|مرسی|ممنون|تشکر", re.I)

    def reply(self, messages):
        text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break

        if self._HELLO_RE.match(text):
            return (
                "Hello! I'm **Pumma**, built by the cyber-kk team. "
                "Right now I'm running in offline mode, so my brain is limited — "
                "but I can still do math, and I always answer honestly. "
                "Connect a model in **Settings** to unlock my full power."
            )

        if self._IDENTITY_RE.search(text):
            return (
                "I'm **Pumma** — an AI assistant created by the **cyber-kk** "
                "development team (%s). My engine is based on DeepSeek-Coder "
                "technology. Right now I'm running in **offline mode** (no model "
                "connected), so I can't think deeply yet. Open **Settings** and "
                "connect any OpenAI-compatible API to bring me fully online." % TEAM_URL
            )

        if self._THANKS_RE.search(text) and len(text) < 40:
            return "You're welcome! — Pumma, by cyber-kk."

        math = _safe_math(text)
        if math is not None:
            return (
                "**Pumma Core (offline)** computed it for you:\n\n"
                "```python\nprint(%s)   # -> %s\n```\n"
                "Connect a full model in Settings for real reasoning."
                % (text, math)
            )

        return (
            "**Pumma Core (offline mode)**\n\n"
            "I'm Pumma, by the cyber-kk team — but no model brain is connected "
            "yet, so I can only handle simple things (like math: try `12*(3+4)`).\n\n"
            "To wake me up fully:\n"
            "1. Open **Settings** (gear icon, top right)\n"
            "2. Pick *OpenAI-compatible API*\n"
            "3. Enter the Base URL, API key and model name\n"
            "4. Save — I'll use that brain from the next message on."
        )


def _safe_math(text):
    """Evaluate pure arithmetic with the AST module (no eval, no names)."""
    cleaned = text.strip().rstrip("?!.؟")
    cleaned = cleaned.replace("×", "*").replace("÷", "/").replace("^", "**")
    if not re.fullmatch(r"[\d\s\+\-\*/%\(\)\.]+", cleaned) or not re.search(r"\d", cleaned):
        return None
    try:
        node = ast.parse(cleaned, mode="eval")
    except SyntaxError:
        return None
    for sub in ast.walk(node):
        if not isinstance(sub, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                                ast.FloorDiv, ast.Pow, ast.USub, ast.UAdd)):
            return None
        if isinstance(sub, ast.Constant) and not isinstance(sub.value, (int, float)):
            return None
    try:
        return eval(compile(node, "<math>", "eval"))
    except ZeroDivisionError:
        return "division by zero"
    except Exception:
        return None


# --------------------------------------------------------------------------
# PummaCore - routing
# --------------------------------------------------------------------------
class PummaCore:
    def __init__(self, base_dir):
        self.base = base_dir
        self.bridge = os.path.join(base_dir, "zai_bridge.mjs")
        self._zai_ok = None  # None = unknown, True/False after first try
        self.offline = PummaOffline()
        self.server_cfg = self._load_server_cfg()

    # -- config ------------------------------------------------------------
    def _load_server_cfg(self):
        path = os.path.join(self.base, "pumma_config.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
            except Exception:
                pass
        return {}

    # -- provider selection --------------------------------------------------
    def active_provider(self, cfg=None):
        c = cfg or {}
        if c.get("provider") == "openai" and c.get("api_key"):
            return "openai-compat"
        if c.get("provider") == "offline":
            return self.offline.NAME
        if c.get("provider") == "auto" or not c.get("provider"):
            sc = self.server_cfg.get("openai_compat") or {}
            if sc.get("api_key"):
                return "openai-compat (server)"
            if self._zai_available():
                return "zai"
            return self.offline.NAME
        return "auto"

    def _zai_available(self):
        if self._zai_ok is not None:
            return self._zai_ok
        self._zai_ok = bool(shutil.which("node")) and os.path.isfile(self.bridge)
        if self._zai_ok:
            try:
                self._zai_ok = _zai_bridge(self.bridge, [
                    {"role": "user", "content": "ping"}
                ]) is not None
            except Exception:
                self._zai_ok = False
        return self._zai_ok

    def warmup(self):
        """Probe the zai bridge once at boot so the health endpoint is accurate."""
        self._zai_available()

    # -- main entry ----------------------------------------------------------
    def respond(self, messages, cfg=None):
        """Returns (reply, provider_name, error). error is None on success."""
        c = cfg if isinstance(cfg, dict) else {}
        want = c.get("provider") or self.server_cfg.get("provider") or "auto"

        # explicit per-request backend
        if want == "openai" and c.get("api_key"):
            try:
                reply = _openai_compat(
                    [{"role": m["role"], "content": m["content"]} for m in messages],
                    c.get("base_url") or "",
                    c["api_key"],
                    c.get("model") or "",
                )
                return reply, "openai-compat", None
            except Exception as e:
                return None, "openai-compat", "Backend error: %s" % _clean_err(e)

        if want == "offline":
            return self.offline.reply(messages), self.offline.NAME, None

        # auto: server config -> zai -> offline
        sc = self.server_cfg.get("openai_compat") or {}
        if sc.get("api_key"):
            try:
                reply = _openai_compat(
                    [{"role": m["role"], "content": m["content"]} for m in messages],
                    sc.get("base_url") or "",
                    sc["api_key"],
                    sc.get("model") or "",
                )
                return reply, "openai-compat (server)", None
            except Exception as e:
                return None, "openai-compat (server)", "Backend error: %s" % _clean_err(e)

        if self._zai_available():
            full = [{"role": "system", "content": IDENTITY_PROMPT}] + [
                {"role": m["role"], "content": m["content"]} for m in messages
            ]
            try:
                reply = _zai_bridge(self.bridge, full)
                return reply, "zai", None
            except Exception as e:
                # a failing bridge falls back so the user is never stuck
                return self.offline.reply(messages), self.offline.NAME, None

        return self.offline.reply(messages), self.offline.NAME, None


def _clean_err(e):
    s = str(e)
    if "urlopen error" in s:
        s = s.split("urlopen error")[-1].strip(" <>")
    if "HTTP Error" in s:
        s = re.sub(r"HTTP Error \d+.*?:\s*", "", s)
    return s[:220]
