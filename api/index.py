"""Health check endpoint - Flask format for Vercel."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api", methods=["GET"])
@app.route("/api/", methods=["GET"])
def handler():
    return jsonify({
        "service": "MPRG - Multi-Path Reasoning Guard",
        "status": "running",
        "endpoints": [
            "POST /api/analyze - Run MPRG analysis",
            "GET /api/history - Get recent analyses",
            "GET /api/task?id=<id> - Get specific task analysis",
            "POST /api/override - Override gate decision",
            "GET /api/patterns - Get fragile patterns"
        ]
    })
