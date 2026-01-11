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
        from mprg.pipeline import OmniPathPipeline
        _pipeline = OmniPathPipeline(
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
        "service": "OmniPath - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/generate - Generate reasoning analysis",
            "POST /api/tasks - Create and run a task",
            "GET /api/tasks - List recent tasks",
            "GET /api/tasks/<id> - Get task details",
            "POST /api/analyze - Run OmniPath analysis",
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
        bundle = generator.generate(data["user_prompt"], num_agents=data.get("num_agents"))
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
        
        bundle = generator.generate(
            data["input_text"],
            num_agents=data.get("num_agents")
        )
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


# ============ OmniPath Analysis Endpoints ============


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
        result = pipeline.analyze(data["task"], num_agents=data.get("num_agents"))
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


@app.route("/tasks/<task_id>/execute", methods=["POST"])
@app.route("/api/tasks/<task_id>/execute", methods=["POST", "OPTIONS"])
def execute_convergent_plan(task_id):
    """Execute the plan from the largest/most convergent family using Claude."""
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        store = get_store()
        task = store.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        
        families = task.get("families", [])
        if not families:
            return jsonify({
                "error": "No families found. Cannot execute without convergent reasoning."
            }), 400
        
        # Find the largest family (most convergent)
        largest_family = max(families, key=lambda f: len(f.get("run_ids", [])))
        family_size = len(largest_family.get("run_ids", []))
        
        if family_size < 2:
            return jsonify({
                "error": "No convergent family detected (largest family has < 2 runs).",
                "recommendation": "Need more agreement between agents before execution."
            }), 400
        
        # Get the representative run from the largest family
        rep_run_id = largest_family.get("rep_run_id")
        runs = store.get_runs(task_id)
        rep_run = next((r for r in runs if r.get("_id") == rep_run_id), None)
        
        if not rep_run:
            return jsonify({"error": "Representative run not found."}), 404
        
        # Extract the plan from the representative run
        plan_steps = rep_run.get("plan_steps", [])
        assumptions = rep_run.get("assumptions", [])
        original_answer = rep_run.get("final_answer", "")
        input_text = task.get("input_text", "")
        
        # Execute with Claude
        execution_result = _execute_plan_claude(
            input_text=input_text,
            plan_steps=plan_steps,
            assumptions=assumptions,
            original_answer=original_answer,
            family_size=family_size,
            total_runs=len(runs),
        )
        
        # Store the execution result
        store.update_task(task_id, {
            "execution_result": execution_result,
            "executed_family_id": largest_family.get("family_id"),
            "executed_family_size": family_size,
        })
        
        return jsonify({
            "success": True,
            "family_id": largest_family.get("family_id"),
            "family_size": family_size,
            "convergence_ratio": round(family_size / len(runs), 2) if runs else 0,
            "execution_result": execution_result,
        })
        
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


def _execute_plan_claude(
    input_text: str,
    plan_steps: list,
    assumptions: list,
    original_answer: str,
    family_size: int,
    total_runs: int,
) -> dict:
    """Run the final executor agent using Claude API."""
    import requests
    
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return {"error": "Anthropic API key not configured", "executed": False}
    
    plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan_steps))
    assumptions_text = "\n".join(f"- {a}" for a in assumptions) if assumptions else "None specified"
    
    prompt = f"""You are a Final Executor Agent. Your job is to execute a verified reasoning plan that has achieved consensus across multiple AI agents.

## Context
- Original Task: {input_text}
- Convergence: {family_size}/{total_runs} agents agreed on this reasoning path
- This plan has been validated as the most robust approach

## Verified Plan to Execute
{plan_text}

## Assumptions Made
{assumptions_text}

## Original Proposed Answer
{original_answer}

## Your Task
Execute this plan step by step and provide:
1. The final result/answer with complete details
2. A confidence assessment based on the reasoning quality
3. Any caveats or limitations discovered during execution

Respond in JSON format:
{{
    "final_result": "The complete executed result/answer",
    "confidence": "HIGH/MEDIUM/LOW",
    "reasoning_summary": "Brief summary of how you arrived at this result",
    "caveats": ["Any limitations or conditions"],
    "executed_steps": ["Summary of each step executed"]
}}"""

    try:
        base_url = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        
        response = requests.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 2048,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        response.raise_for_status()
        
        response_data = response.json()
        content = response_data.get("content", [{}])[0].get("text", "").strip()
        
        import json
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
                result["executed"] = True
                result["model_used"] = model
                return result
        except json.JSONDecodeError:
            pass
        
        return {
            "final_result": content,
            "executed": True,
            "confidence": "MEDIUM",
            "model_used": model,
        }
        
    except Exception as e:
        return {"error": str(e), "executed": False}


# Catch-all for debugging
@app.route("/<path:path>")
def catch_all(path):
    return jsonify({
        "error": "Route not found",
        "requested_path": path,
        "available_routes": ["/", "/generate", "/tasks", "/analyze", "/history", "/tasks/<id>/execute"]
    }), 404
