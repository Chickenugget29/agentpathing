"""Override gate decision - Flask format for Vercel."""

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/api/override", methods=["POST", "OPTIONS"])
def handler():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response
    
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
