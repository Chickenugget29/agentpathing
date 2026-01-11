"""Minimal HTTP API for the OmniPath Generator."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from mprg.generator import ReasoningGuardGenerator
from mprg.task_analysis import compute_families_and_robustness
from mprg.task_store import TaskStore


load_dotenv()

app = Flask(__name__)
CORS(app)

FRONTEND_DIST = Path(__file__).resolve().parent / "front_end" / "dist"
FRONTEND_DIST_STR = str(FRONTEND_DIST)

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
        bundle = generator.generate(prompt, num_agents=data.get("num_agents"))
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
        bundle = generator.generate(input_text, num_agents=data.get("num_agents"))
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
                    "error": run.get("error"),
                    "canonical_text": run.get("canonical_text"),
                    "intent": run.get("intent"),
                    "raw_json": run,
                },
            )
        _analyze_task(task_id)
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
                "error": run.get("error"),
                "canonical_text": run.get("canonical_text"),
                "intent": run.get("intent"),
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


@app.route("/tasks/<task_id>/execute", methods=["POST"])
def execute_convergent_plan(task_id: str):
    """
    Execute the plan from the largest/most convergent family.
    This runs a final agent that takes the representative plan and generates
    the actual result by following the reasoning steps.
    """
    try:
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
        
        # Build the execution prompt
        execution_result = _execute_plan(
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


def _execute_plan(
    input_text: str,
    plan_steps: list,
    assumptions: list,
    original_answer: str,
    family_size: int,
    total_runs: int,
) -> dict:
    """Run the executor agent to generate a final result from the convergent plan."""
    import requests
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return {"error": "OpenAI API key not configured", "executed": False}
    
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
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,  # Lower temp for execution
            },
            timeout=60,
        )
        response.raise_for_status()
        
        content = response.json()["choices"][0]["message"]["content"].strip()
        
        # Try to parse JSON response
        import json
        try:
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
                result["executed"] = True
                result["raw_response"] = content
                return result
        except json.JSONDecodeError:
            pass
        
        # Fallback if not valid JSON
        return {
            "final_result": content,
            "executed": True,
            "confidence": "MEDIUM",
            "raw_response": content,
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "executed": False,
        }


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    """Serve the React frontend bundle for manual testing."""
    if not FRONTEND_DIST.exists():
        return jsonify({
            "error": "frontend_build_missing",
            "message": "Run 'npm install && npm run build' inside front_end/ to generate dist assets.",
        }), 503

    asset_path = FRONTEND_DIST / path if path else FRONTEND_DIST / "index.html"
    if path and asset_path.is_file():
        return send_from_directory(FRONTEND_DIST_STR, path)
    return send_from_directory(FRONTEND_DIST_STR, "index.html")


def _analyze_task(task_id: str) -> None:
    runs = store.get_runs(task_id)
    try:
        families, robustness, analysis_error, metrics = compute_families_and_robustness(
            runs
        )
        if metrics.get("valid_runs", 0) < 2:
            families = []
            robustness = "INSUFFICIENT_DATA"
        family_payload = [
            {
                "family_id": family.family_id,
                "rep_run_id": family.rep_run_id,
                "run_ids": family.run_ids,
            }
            for family in families
        ]
        _update_runs_with_families(runs, families)
        store.update_task_analysis(
            task_id,
            families=family_payload,
            num_families=metrics.get("num_families", len(family_payload)),
            robustness_status=robustness,
            analysis_error=analysis_error,
            threshold_used=metrics.get("threshold_used"),
            clustering_method=metrics.get("clustering_method"),
            family_sizes=[len(family.run_ids) for family in families],
        )
        if robustness == "INSUFFICIENT_DATA":
            store.update_task(task_id, {"robustness_status": "INSUFFICIENT_DATA"})
        valid_runs = metrics.get("valid_runs", 0)
        mode_counts = {
            "min_similarity": metrics.get("min_similarity"),
            "avg_similarity": metrics.get("avg_similarity"),
            "max_similarity": metrics.get("max_similarity"),
            "sample_top5_similarities": metrics.get("sample_top5_similarities"),
            "mode_counts": metrics.get("mode_counts"),
        }
        print(
            "[analysis]",
            "valid_runs=",
            valid_runs,
            "similarity_stats=",
            mode_counts,
            "num_families=",
            len(family_payload),
            "robustness=",
            robustness,
        )
    except Exception as exc:
        store.update_task_analysis(
            task_id,
            families=[],
            num_families=0,
            robustness_status="ERROR",
            analysis_error=str(exc),
        )
        print("[analysis] error:", exc)


def _update_runs_with_families(runs, families) -> None:
    run_family_map = {}
    for family in families:
        for run_id in family.run_ids:
            run_family_map[run_id] = (family.family_id, family.rep_run_id)

    for run in runs:
        run_id = run.get("_id")
        if not run_id:
            continue
        family_info = run_family_map.get(run_id)
        if not family_info:
            continue
        family_id, rep_id = family_info
        embedding = run.get("raw_json", {}).get("embedding_vector") or []
        rep_run = next((r for r in runs if r.get("_id") == rep_id), None)
        similarity = None
        if rep_run and rep_run.get("raw_json", {}).get("embedding_vector"):
            from mprg.task_analysis import _cosine_similarity  # local import

            similarity = _cosine_similarity(
                embedding, rep_run["raw_json"]["embedding_vector"]
            )
        store.runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "family_id": family_id,
                    "family_similarity": similarity,
                    "family_representative_run_id": rep_id,
                }
            },
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"🚀 OmniPath Generator on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
