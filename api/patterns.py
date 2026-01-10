"""Get fragile patterns - Flask format for Vercel."""

from flask import Flask, jsonify
import os

app = Flask(__name__)


def get_patterns():
    try:
        from pymongo import MongoClient
        
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return []
            
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        collection = client.mprg.robustness_results
        
        pipeline = [
            {"$match": {"robustness_score": "FRAGILE"}},
            {"$group": {
                "_id": "$task_prompt",
                "count": {"$sum": 1},
                "last_seen": {"$max": "$created_at"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        results = list(collection.aggregate(pipeline))
        for r in results:
            if "last_seen" in r and hasattr(r["last_seen"], "isoformat"):
                r["last_seen"] = r["last_seen"].isoformat()
        return results
    except Exception:
        return []


@app.route("/api/patterns", methods=["GET"])
def handler():
    patterns = get_patterns()
    return jsonify({"patterns": patterns})
