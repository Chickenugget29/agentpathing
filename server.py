"""Flask API server for OmniPath - Render deployment."""

from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Lazy load pipeline to avoid startup issues
_pipeline = None

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


@app.route("/")
def home():
    """Health check."""
    return jsonify({
        "service": "OmniPath - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/analyze - Run OmniPath analysis",
            "GET /api/history - Get recent analyses",
            "GET /api/task?id=<id> - Get specific task analysis",
            "POST /api/override - Override gate decision",
            "GET /api/patterns - Get fragile patterns"
        ]
    })


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def analyze():
    """Run OmniPath analysis on a task."""
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


@app.route("/api/history", methods=["GET"])
def history():
    """Get recent analysis history."""
    limit = request.args.get("limit", 10, type=int)
    
    pipeline = get_pipeline()
    if pipeline.ledger:
        results = pipeline.ledger.get_recent_analyses(limit)
        return jsonify({"analyses": results})
    else:
        return jsonify({
            "analyses": [],
            "note": "MongoDB not configured - no history available"
        })


@app.route("/api/task", methods=["GET"])
def get_task():
    """Get specific task analysis."""
    task_id = request.args.get("id")
    
    if not task_id:
        return jsonify({"error": "Missing 'id' query parameter"}), 400
    
    pipeline = get_pipeline()
    if pipeline.ledger:
        analysis = pipeline.ledger.get_task_analysis(task_id)
        if analysis:
            return jsonify(analysis)
        return jsonify({"error": "Task not found"}), 404
    else:
        return jsonify({"error": "MongoDB not configured"}), 503


@app.route("/api/override", methods=["POST", "OPTIONS"])
def override():
    """Override a gate decision."""
    if request.method == "OPTIONS":
        return "", 200
    
    data = request.get_json() or {}
    
    if "task_id" not in data or "confirmation" not in data:
        return jsonify({
            "error": "Missing 'task_id' or 'confirmation' in request"
        }), 400
        
    return jsonify({
        "status": "override_accepted",
        "task_id": data["task_id"],
        "message": "Gate decision overridden. Proceed with caution."
    })


@app.route("/api/patterns", methods=["GET"])
def fragile_patterns():
    """Get historical fragile patterns."""
    pipeline = get_pipeline()
    if pipeline.ledger:
        patterns = pipeline.ledger.get_fragile_patterns()
        return jsonify({"patterns": patterns})
    else:
        return jsonify({"patterns": []})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Starting OmniPath server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
