"""Main MPRG analysis endpoint."""

import json
import os
import sys


def handler(request):
    """Vercel Python serverless function handler."""
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }
    
    # Parse request body
    try:
        body = request.body
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, AttributeError):
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Invalid JSON"})
        }
    
    if "task" not in data:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Missing 'task' in request body"})
        }
    
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
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(result_to_dict(result), default=str)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }
