"""Get specific task analysis - MongoDB only."""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse


def get_task_analysis(task_id: str):
    """Lazy import and query."""
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return None
            
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client.mprg
        
        # Get robustness result
        result = db.robustness_results.find_one({"task_id": task_id})
        if not result:
            return None
            
        # Get agent outputs
        outputs = list(db.agent_outputs.find({"task_id": task_id}))
        
        # Get reasoning traces
        output_ids = [str(o["_id"]) for o in outputs]
        traces = list(db.reasoning_traces.find({
            "agent_output_id": {"$in": output_ids}
        }))
        
        # Get families
        families = list(db.reasoning_families.find({"task_id": task_id}))
        
        # Serialize all documents
        def serialize(doc):
            if doc is None:
                return None
            serialized = {}
            for k, v in doc.items():
                if isinstance(v, ObjectId):
                    serialized[k] = str(v)
                elif hasattr(v, "isoformat"):
                    serialized[k] = v.isoformat()
                else:
                    serialized[k] = v
            return serialized
        
        return {
            "result": serialize(result),
            "agent_outputs": [serialize(o) for o in outputs],
            "reasoning_traces": [serialize(t) for t in traces],
            "families": [serialize(f) for f in families],
        }
    except Exception as e:
        return {"error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query params for task_id
        query = parse_qs(urlparse(self.path).query)
        task_id = query.get('id', [None])[0]
        
        if not task_id:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing 'id' query parameter"}).encode())
            return
        
        analysis = get_task_analysis(task_id)
        
        if analysis is None:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Task not found"}).encode())
            return
        
        if "error" in analysis and len(analysis) == 1:
            self.send_response(503)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(analysis).encode())
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(analysis).encode())
        return
