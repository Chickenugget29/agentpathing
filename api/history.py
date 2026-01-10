"""Get recent analysis history - Flask format for Vercel."""

from flask import Flask, request, jsonify
import os

app = Flask(__name__)


def get_history(limit=10):
    try:
        from pymongo import MongoClient
        
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return None, "MongoDB not configured"
            
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        collection = client.mprg.robustness_results
        
        results = list(collection.find().sort("created_at", -1).limit(limit))
        analyses = []
        for r in results:
            r["_id"] = str(r["_id"])
            if "created_at" in r and hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
            analyses.append(r)
        return analyses, None
    except Exception as e:
        return [], str(e)


@app.route("/api/history", methods=["GET"])
def handler():
    limit = request.args.get('limit', 10, type=int)
    analyses, error = get_history(limit)
    
    if analyses is None:
        return jsonify({"analyses": [], "note": error})
    elif error:
        return jsonify({"analyses": analyses, "error": error})
    else:
        return jsonify({"analyses": analyses})
