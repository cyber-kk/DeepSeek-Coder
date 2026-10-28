#!/usr/bin/env python3
# Pumma - AI assistant server by the cyber-kk team (https://github.com/cyber-kk)
# Run:  python server.py   ->   http://localhost:5000
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "web")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from flask import Flask, jsonify, request, send_from_directory

from pumma import PummaCore
from sandbox import run_python

app = Flask(__name__, static_folder=None)
core = PummaCore(BASE)


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/web/<path:filename>")
def web_files(filename):
    return send_from_directory(WEB, filename)


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "app": "Pumma",
            "team": "cyber-kk",
            "team_url": "https://github.com/cyber-kk",
            "provider": core.active_provider(),
        }
    )


@app.post("/api/chat")
def chat():
    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "No messages provided."}), 400
    # keep the conversation bounded
    if len(messages) > 40:
        messages = messages[-40:]
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            return jsonify({"error": "Invalid message format."}), 400
        if not isinstance(m.get("content"), str):
            return jsonify({"error": "Invalid message content."}), 400

    reply, provider, error = core.respond(messages, data.get("config"))
    if error is not None:
        return jsonify({"error": error, "provider": provider}), 502
    return jsonify({"reply": reply, "provider": provider})


@app.post("/api/run")
def run_code():
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "No code provided."}), 400
    if len(code) > 100_000:
        return jsonify({"error": "Code too large (max 100 KB)."}), 400
    return jsonify(run_python(code))


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    import threading

    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print("  Pumma  -  by cyber-kk (https://github.com/cyber-kk)")
    print(f"  Chat bot ready:  http://localhost:{port}")
    # probe backends in the background so the server listens immediately
    threading.Thread(target=core.warmup, daemon=True).start()
    app.run(host=host, port=port, debug=False, threaded=True)
