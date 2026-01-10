"""Main Flask API for Vercel - all endpoints in one file."""

from __future__ import annotations

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Lazy load components
_pipeline = None
_generator = None
_store = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from mprg.pipeline import MPRGPipeline
        _pipeline = MPRGPipeline(
            voyage_key=os.getenv("VOYAGE_API_KEY"),
            openai_key=os.getenv("OPENAI_API_KEY"),
            mongodb_uri=os.getenv("MONGODB_URI")
        )
    return _pipeline


def get_generator():
    global _generator
    if _generator is None:
        from mprg.generator import ReasoningGuardGenerator
        _generator = ReasoningGuardGenerator(
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
    return _generator


def get_store():
    global _store
    if _store is None:
        from mprg.task_store import TaskStore
        _store = TaskStore(os.getenv("MONGODB_URI"))
    return _store


# ============ Health Check ============


@app.route("/")
@app.route("/api")
@app.route("/api/")
def home():
    return jsonify({
        "service": "MPRG - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/generate - Generate reasoning analysis",
            "POST /api/tasks - Create and run a task",
            "GET /api/tasks - List recent tasks",
            "GET /api/tasks/<id> - Get task details",
            "POST /api/analyze - Run MPRG analysis",
            "GET /api/history - Get analysis history",
        ]
    })


# ============ Generator Endpoints ============


@app.route("/generate", methods=["POST"])
@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    if "user_prompt" not in data:
        return jsonify({"error": "Missing 'user_prompt' in request body."}), 400
    
    try:
        generator = get_generator()
        bundle = generator.generate(data["user_prompt"])
        return jsonify(bundle)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tasks", methods=["POST"])
@app.route("/api/tasks", methods=["POST", "OPTIONS"])
def create_task():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    if "input_text" not in data:
        return jsonify({"error": "Missing 'input_text' in request body."}), 400
    
    try:
        generator = get_generator()
        store = get_store()
        
        task_id = store.create_task(data["input_text"])
        store.update_task(task_id, {"status": "RUNNING"})
        
        bundle = generator.generate(data["input_text"])
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tasks", methods=["GET"])
@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    limit = request.args.get("limit", 20, type=int)
    try:
        store = get_store()
        tasks = store.list_tasks(limit=limit)
        return jsonify({"tasks": tasks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tasks/<task_id>", methods=["GET"])
@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task_by_id(task_id):
    try:
        store = get_store()
        task = store.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        runs = store.get_runs(task_id)
        return jsonify({"task": task, "runs": runs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tasks/<task_id>/runs", methods=["POST"])
@app.route("/api/tasks/<task_id>/runs", methods=["POST", "OPTIONS"])
def create_run(task_id):
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    if "run" not in data:
        return jsonify({"error": "Missing 'run' in request body."}), 400
    
    try:
        store = get_store()
        run = data["run"]
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ MPRG Analysis Endpoints ============


@app.route("/analyze", methods=["POST"])
@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    if "task" not in data:
        return jsonify({"error": "Missing 'task' in request body"}), 400
    
    try:
        from mprg.pipeline import result_to_dict
        pipeline = get_pipeline()
        result = pipeline.analyze(data["task"])
        return jsonify(result_to_dict(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history", methods=["GET"])
@app.route("/api/history", methods=["GET"])
def history():
    limit = request.args.get("limit", 10, type=int)
    pipeline = get_pipeline()
    if pipeline.ledger:
        results = pipeline.ledger.get_recent_analyses(limit)
        return jsonify({"analyses": results})
    return jsonify({"analyses": [], "note": "MongoDB not configured"})


@app.route("/task", methods=["GET"])
@app.route("/api/task", methods=["GET"])
def get_task():
    task_id = request.args.get("id")
    if not task_id:
        return jsonify({"error": "Missing 'id' query parameter"}), 400
    
    pipeline = get_pipeline()
    if pipeline.ledger:
        analysis = pipeline.ledger.get_task_analysis(task_id)
        if analysis:
            return jsonify(analysis)
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"error": "MongoDB not configured"}), 503


@app.route("/override", methods=["POST"])
@app.route("/api/override", methods=["POST", "OPTIONS"])
def override():
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    if "task_id" not in data or "confirmation" not in data:
        return jsonify({"error": "Missing 'task_id' or 'confirmation'"}), 400
    
    return jsonify({
        "status": "override_accepted",
        "task_id": data["task_id"],
        "message": "Gate decision overridden."
    })


@app.route("/patterns", methods=["GET"])
@app.route("/api/patterns", methods=["GET"])
def patterns():
    pipeline = get_pipeline()
    if pipeline.ledger:
        return jsonify({"patterns": pipeline.ledger.get_fragile_patterns()})
    return jsonify({"patterns": []})


# Catch-all for debugging
@app.route("/<path:path>")
def catch_all(path):
    return jsonify({
        "error": "Route not found",
        "requested_path": path,
        "available_routes": ["/", "/generate", "/tasks", "/analyze", "/history"]
    }), 404
