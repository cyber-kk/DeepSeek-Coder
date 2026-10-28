<p align="center">
  <img width="120px" alt="Pumma logo" src="Pumma/web/logo.svg">
</p>

<h1 align="center">Pumma</h1>

<p align="center"><b>Ask anything. Pumma delivers.</b></p>
<p align="center">An AI assistant by the <a href="https://github.com/cyber-kk"><b>cyber-kk</b></a> development team, converted from DeepSeek-Coder technology.</p>

---

## What is Pumma

Pumma is a complete AI chat assistant built on top of DeepSeek-Coder technology. The cyber-kk team converted the DeepSeek-Coder project into **Pumma**: a named assistant with its own identity, a do-it mindset (Pumma always works toward delivering what you ask instead of stopping at "impossible"), expert programming skills, and a clean chat interface that runs anywhere — including 32-bit mobile devices.

Pumma is two things in one repository:

1. **The Pumma chat bot** (`Pumma/`) — a ready-to-run Python chat server with a web UI, a Python code runner, and a pluggable engine. This is the part you will actually use every day.
2. **The model technology** (`demo/`, `finetune/`, `Evaluation/`) — the original DeepSeek-Coder training, fine-tuning, demo and evaluation code, converted and maintained as the Pumma engine base.

## Quick start (localhost:5000)

### PC / laptop

```bash
pip install -r Pumma/requirements.txt
cd Pumma
python server.py
```

Then open **http://localhost:5000** in your browser.

### Android (Termux, including 32-bit phones)

Pumma is pure Python + vanilla JS — no heavy frameworks, no native builds:

```bash
pkg install python
pip install flask
cd Pumma
python server.py
```

Open **http://localhost:5000** in your phone browser. To open Pumma from another device on the same Wi-Fi:

```bash
HOST=0.0.0.0 python server.py
```

## Connecting a brain (the model)

This repository contains model *code*, not model *weights* — DeepSeek-Coder weights are multi-GB files that cannot run on a 32-bit phone. Pumma solves this cleanly: the identity and personality live in Pumma, the thinking is pluggable. Three options, picked automatically or in **Settings** (gear icon):

| Option | What it is | How to enable |
|---|---|---|
| **OpenAI-compatible API** | Any endpoint speaking `/chat/completions`: DeepSeek API, OpenRouter, Ollama, llama.cpp server, LM Studio, ... | Settings → *OpenAI-compatible API* → Base URL / API key / model name |
| **zai bridge** | Bundled bridge used for live previews in the Z.ai sandbox | Automatic when `node` + `z-ai-web-dev-sdk` are available (`npm install` inside `Pumma/`) |
| **Pumma Core (offline)** | Honest built-in fallback: identity, math, guidance — works with zero setup | Settings → *Pumma Core (offline)*, or used automatically when nothing else is available |

Server-wide backend config (optional): copy `pumma_config.example.json` to `pumma_config.json` and fill it in. The browser-side config from Settings wins when both exist.

### Recommended presets

- **DeepSeek API**: base URL `https://api.deepseek.com/v1`, model `deepseek-chat` (or `deepseek-coder`)
- **OpenRouter**: base URL `https://openrouter.ai/api/v1`, model e.g. `deepseek/deepseek-chat`
- **Ollama on a PC**: base URL `http://<pc-ip>:11434/v1`, model e.g. `deepseek-coder:6.7b`
- **llama.cpp server**: base URL `http://<host>:8080/v1`, your local model name

## Running Python code

Every ` ```python ` block Pumma writes gets a **Run** button in the chat. The code executes in a restricted sandbox (fresh isolated interpreter, network/process modules blocked, 512 MB memory cap, 12-second hard timeout, 64 KB output cap) and the output appears under the block. It is a convenience sandbox for personal local use — not a hardened security boundary.

## The Pumma identity

Pumma's self-image ("I'm Pumma, built by the cyber-kk team") and its do-it personality are defined in `Pumma/pumma.py` (`IDENTITY_PROMPT`) and applied to every connected brain, so whoever you talk to — Pumma always answers as **Pumma**.

## Project structure

```
DeepSeek-Coder/
├── Pumma/                    the chat bot
│   ├── server.py             Flask server -> http://localhost:5000
│   ├── pumma.py              identity, engine routing, offline core
│   ├── sandbox.py            restricted Python code runner
│   ├── zai_bridge.mjs        optional z-ai bridge (sandbox preview)
│   ├── pumma_config.example.json
│   └── web/                  chat UI (vanilla JS, mobile-first, dark)
├── demo/                     model demo (Gradio, needs CUDA)
├── finetune/                 fine-tuning pipeline
├── Evaluation/               HumanEval / MBPP / DS-1000 / LeetCode harnesses
└── README.md                 this file
```

## Team

Pumma is developed and maintained by the **cyber-kk** team → [github.com/cyber-kk](https://github.com/cyber-kk).
