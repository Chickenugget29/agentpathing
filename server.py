"""Flask API server for MPRG.

Provides REST endpoints for:
- Running MPRG analysis
- Getting analysis history
- Overriding gate decisions
"""

from __future__ import annotations

import os
from flask import Flask, request, jsonify
from flask_cors import CORS

from mprg.pipeline import MPRGPipeline, result_to_dict
from mprg.db import ReasoningLedger


app = Flask(__name__)
CORS(app)

# Initialize pipeline
pipeline = MPRGPipeline(
    voyage_key=os.getenv("VOYAGE_API_KEY"),
    openai_key=os.getenv("OPENAI_API_KEY"),
    mongodb_uri=os.getenv("MONGODB_URI")
)


@app.route("/")
def home():
    """Health check."""
    return jsonify({
        "service": "MPRG - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/analyze - Run MPRG analysis",
            "GET /api/history - Get recent analyses",
            "GET /api/task/<id> - Get specific task analysis",
            "POST /api/override - Override gate decision"
        ]
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Run MPRG analysis on a task.
    
    Request body:
    {
        "task": "Your task prompt here"
    }
    """
    data = request.get_json()
    
    if not data or "task" not in data:
        return jsonify({"error": "Missing 'task' in request body"}), 400
        
    task = data["task"]
    
    try:
        result = pipeline.analyze(task)
        return jsonify(result_to_dict(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["GET"])
def history():
    """Get recent analysis history."""
    limit = request.args.get("limit", 10, type=int)
    
    if pipeline.ledger:
        results = pipeline.ledger.get_recent_analyses(limit)
        return jsonify({"analyses": results})
    else:
        return jsonify({
            "analyses": [],
            "note": "MongoDB not configured - no history available"
        })


@app.route("/api/task/<task_id>", methods=["GET"])
def get_task(task_id: str):
    """Get specific task analysis."""
    if pipeline.ledger:
        analysis = pipeline.ledger.get_task_analysis(task_id)
        if analysis:
            return jsonify(analysis)
        return jsonify({"error": "Task not found"}), 404
    else:
        return jsonify({"error": "MongoDB not configured"}), 503


@app.route("/api/override", methods=["POST"])
def override():
    """Override a gate decision.
    
    Request body:
    {
        "task_id": "task_abc123",
        "confirmation": "I accept the risk"
    }
    """
    data = request.get_json()
    
    if not data or "task_id" not in data or "confirmation" not in data:
        return jsonify({
            "error": "Missing 'task_id' or 'confirmation' in request"
        }), 400
        
    return jsonify({
        "status": "override_accepted",
        "task_id": data["task_id"],
        "message": "Gate decision overridden. Proceed with caution."
    })


@app.route("/api/fragile-patterns", methods=["GET"])
def fragile_patterns():
    """Get historical fragile patterns - for demo."""
    if pipeline.ledger:
        patterns = pipeline.ledger.get_fragile_patterns()
        return jsonify({"patterns": patterns})
    else:
        return jsonify({"patterns": []})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Starting MPRG server on http://localhost:{port}")
    print("   Endpoints:")
    print("   - POST /api/analyze - Run analysis")
    print("   - GET  /api/history - View history")
    print()
    app.run(host="0.0.0.0", port=port, debug=True)
