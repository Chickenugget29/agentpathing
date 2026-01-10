"""Main MPRG analysis endpoint - Flask format for Vercel."""

from flask import Flask, request, jsonify
import os
import sys

app = Flask(__name__)


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def handler():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response
    
    data = request.get_json() or {}
    
    if "task" not in data:
        return jsonify({"error": "Missing 'task' in request body"}), 400
    
    try:
        # Add parent directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from mprg.pipeline import MPRGPipeline, result_to_dict
        
        pipeline = MPRGPipeline(
            voyage_key=os.getenv("VOYAGE_API_KEY"),
            openai_key=os.getenv("OPENAI_API_KEY"),
            mongodb_uri=os.getenv("MONGODB_URI")
        )
        
        result = pipeline.analyze(data["task"])
        return jsonify(result_to_dict(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
