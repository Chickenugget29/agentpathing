"""Get recent analysis history - MongoDB only."""

import json
import os


def get_history(limit=10):
    """Get recent analyses from MongoDB."""
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


def handler(request):
    """Vercel Python serverless function handler."""
    # Parse limit from query
    limit = 10
    if hasattr(request, 'args'):
        limit = int(request.args.get('limit', 10))
    
    analyses, error = get_history(limit)
    
    if analyses is None:
        response = {"analyses": [], "note": error}
    elif error:
        response = {"analyses": analyses, "error": error}
    else:
        response = {"analyses": analyses}
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response)
    }
