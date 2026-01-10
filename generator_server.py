"""Minimal HTTP API for Reasoning Guard Generator."""

from __future__ import annotations

import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from mprg.generator import ReasoningGuardGenerator
from mprg.task_store import TaskStore


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
store = TaskStore(os.getenv("MONGODB_URI"))


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


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data or "input_text" not in data:
        return jsonify({"error": "Missing 'input_text' in request body."}), 400
    input_text = data["input_text"]
    try:
        task_id = store.create_task(input_text)
        store.update_task(task_id, {"status": "RUNNING"})
        bundle = generator.generate(input_text)
        runs = bundle.get("runs", [])
        for run in runs:
            summary = run.get("reasoning_summary") or {}
            store.insert_run(
                task_id,
                {
                    "agent_role": run.get("agent_role"),
                    "plan_steps": summary.get("plan_steps", []),
                    "assumptions": summary.get("assumptions", []),
                    "final_answer": summary.get("final_answer", ""),
                    "is_valid": run.get("is_valid", False),
                    "raw_json": run,
                },
            )
        store.update_task(task_id, {"status": "DONE"})
        return jsonify({"task_id": task_id})
    except Exception as exc:
        if "task_id" in locals():
            store.update_task(task_id, {"status": "FAILED"})
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks/<task_id>/runs", methods=["POST"])
def create_run(task_id: str):
    data = request.get_json()
    if not data or "run" not in data:
        return jsonify({"error": "Missing 'run' in request body."}), 400
    run = data["run"]
    try:
        summary = run.get("reasoning_summary") or {}
        run_id = store.insert_run(
            task_id,
            {
                "agent_role": run.get("agent_role"),
                "plan_steps": summary.get("plan_steps", []),
                "assumptions": summary.get("assumptions", []),
                "final_answer": summary.get("final_answer", ""),
                "is_valid": run.get("is_valid", False),
                "raw_json": run,
            },
        )
        return jsonify({"run_id": run_id})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    try:
        task = store.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        runs = store.get_runs(task_id)
        return jsonify({"task": task, "runs": runs})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks", methods=["GET"])
def list_tasks():
    limit = request.args.get("limit", 20, type=int)
    try:
        tasks = store.list_tasks(limit=limit)
        return jsonify({"tasks": tasks})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"🚀 Reasoning Guard Generator on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
