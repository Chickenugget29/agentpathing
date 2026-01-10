"""Main Flask API for Vercel - all endpoints in one file."""

from __future__ import annotations

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Lazy load pipeline
_pipeline = None

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


# Root route - handles /api and /api/
@app.route("/")
@app.route("/api")
@app.route("/api/")
def home():
    """Health check."""
    return jsonify({
        "service": "MPRG - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/analyze - Run MPRG analysis",
            "GET /api/history - Get recent analyses",
            "GET /api/task?id=<id> - Get specific task",
            "POST /api/override - Override gate",
            "GET /api/patterns - Fragile patterns"
        ]
    })


@app.route("/analyze", methods=["POST", "OPTIONS"])
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


@app.route("/override", methods=["POST", "OPTIONS"])
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
        "available_routes": ["/", "/analyze", "/history", "/task", "/override", "/patterns"]
    }), 404
