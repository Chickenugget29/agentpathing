"""Get recent analysis history - MongoDB only, no heavy ML deps."""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse


def get_ledger():
    """Lazy import to keep function small."""
    try:
        from pymongo import MongoClient
        
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return None
            
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        return client.mprg.robustness_results
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Parse query params
        query = parse_qs(urlparse(self.path).query)
        limit = int(query.get('limit', [10])[0])
        
        collection = get_ledger()
        
        if collection:
            try:
                results = list(collection.find().sort("created_at", -1).limit(limit))
                # Serialize ObjectId and datetime
                analyses = []
                for r in results:
                    r["_id"] = str(r["_id"])
                    if "created_at" in r and hasattr(r["created_at"], "isoformat"):
                        r["created_at"] = r["created_at"].isoformat()
                    analyses.append(r)
                    
                response = {"analyses": analyses}
            except Exception as e:
                response = {"analyses": [], "error": str(e)}
        else:
            response = {
                "analyses": [],
                "note": "MongoDB not configured - no history available"
            }
        
        self.wfile.write(json.dumps(response).encode())
        return
