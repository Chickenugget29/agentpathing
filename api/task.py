"""Get specific task analysis - Flask format for Vercel."""

from flask import Flask, request, jsonify
import os

app = Flask(__name__)


def get_task_analysis(task_id):
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return None, "MongoDB not configured"
            
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client.mprg
        
        result = db.robustness_results.find_one({"task_id": task_id})
        if not result:
            return None, "Task not found"
            
        outputs = list(db.agent_outputs.find({"task_id": task_id}))
        output_ids = [str(o["_id"]) for o in outputs]
        traces = list(db.reasoning_traces.find({
            "agent_output_id": {"$in": output_ids}
        }))
        families = list(db.reasoning_families.find({"task_id": task_id}))
        
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
        }, None
    except Exception as e:
        return None, str(e)


@app.route("/api/task", methods=["GET"])
def handler():
    task_id = request.args.get('id')
    
    if not task_id:
        return jsonify({"error": "Missing 'id' query parameter"}), 400
    
    analysis, error = get_task_analysis(task_id)
    
    if analysis is None:
        status = 404 if error == "Task not found" else 503
        return jsonify({"error": error}), status
    
    return jsonify(analysis)
