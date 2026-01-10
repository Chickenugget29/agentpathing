"""Get fragile patterns - MongoDB only."""

import json
import os


def get_patterns():
    """Get fragile patterns from MongoDB."""
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


def handler(request):
    """Vercel Python serverless function handler."""
    patterns = get_patterns()
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"patterns": patterns})
    }
