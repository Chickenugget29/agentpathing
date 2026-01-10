"""Minimal HTTP API for Reasoning Guard Generator."""

from __future__ import annotations

import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from mprg.generator import ReasoningGuardGenerator


load_dotenv()

app = Flask(__name__)
CORS(app)

generator = ReasoningGuardGenerator(
    provider=os.getenv("LLM_PROVIDER", "openai"),
    openai_key=os.getenv("OPENAI_API_KEY"),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
    anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
    anthropic_base_url=os.getenv("ANTHROPIC_API_BASE"),
    num_agents=int(os.getenv("AGENT_COUNT", "5")),
    enable_embeddings=os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true",
    voyage_key=os.getenv("VOYAGE_API_KEY"),
)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or "user_prompt" not in data:
        return jsonify({"error": "Missing 'user_prompt' in request body."}), 400
    prompt = data["user_prompt"]
    try:
        bundle = generator.generate(prompt)
        return jsonify(bundle)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"🚀 Reasoning Guard Generator on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
