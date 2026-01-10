"""Flask API server for MPRG (Multi-Path Reasoning Guard)."""

from __future__ import annotations

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from mprg.agent_runner import MultiAgentRunner
from mprg.orchestrator import MPRGOrchestrator
from mprg.store import MongoStore


app = Flask(__name__)
CORS(app)

load_dotenv()

store = MongoStore(os.getenv("MONGODB_URI"))
runner = MultiAgentRunner(
    openai_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    num_agents=int(os.getenv("AGENT_COUNT", "4")),
)
orchestrator = MPRGOrchestrator(
    store=store,
    runner=runner,
    plan_threshold=float(os.getenv("PLAN_SIM_THRESHOLD", "0.85")),
    assumption_threshold=float(os.getenv("ASSUMPTION_SIM_THRESHOLD", "0.70")),
)


@app.route("/")
def home():
    """Health check."""
    return jsonify({
        "service": "MPRG - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /tasks - Create + run a task",
            "GET /tasks/<id> - Task status + robustness",
            "GET /tasks/<id>/runs - List agent runs",
            "GET /tasks/<id>/families - List reasoning families"
        ]
    })

@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data or "task" not in data:
        return jsonify({"error": "Missing 'task' in request body"}), 400

    prompt = data["task"]
    try:
        result = orchestrator.create_and_run(prompt)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks/<task_id>", methods=["GET"])
def task_status(task_id: str):
    try:
        task = store.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        if task.get("status") != "COMPLETED":
            orchestrator.resume_task(task_id)
            task = store.get_task(task_id)
        return jsonify(task)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks/<task_id>/runs", methods=["GET"])
def task_runs(task_id: str):
    try:
        runs = store.get_runs(task_id)
        return jsonify({"runs": runs})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/tasks/<task_id>/families", methods=["GET"])
def task_families(task_id: str):
    try:
        task = store.get_task(task_id)
        if task and task.get("status") != "COMPLETED":
            orchestrator.resume_task(task_id)
        families = store.get_families(task_id)
        return jsonify({"families": families})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Starting MPRG server on http://localhost:{port}")
    print("   Endpoints:")
    print("   - POST /tasks")
    print("   - GET  /tasks/<id>")
    print("   - GET  /tasks/<id>/runs")
    print("   - GET  /tasks/<id>/families")
    print()
    app.run(host="0.0.0.0", port=port, debug=True)
