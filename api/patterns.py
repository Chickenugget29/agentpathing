"""Get fragile patterns - MongoDB only, no heavy ML deps."""

from http.server import BaseHTTPRequestHandler
import json
import os


def get_patterns():
    """Lazy import and query."""
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
        # Serialize datetime
        for r in results:
            if "last_seen" in r and hasattr(r["last_seen"], "isoformat"):
                r["last_seen"] = r["last_seen"].isoformat()
        return results
    except Exception:
        return []


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        patterns = get_patterns()
        response = {"patterns": patterns}
        
        self.wfile.write(json.dumps(response).encode())
        return
