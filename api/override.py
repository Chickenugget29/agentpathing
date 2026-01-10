"""Override gate decision - lightweight endpoint."""

import json


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
    
    if "task_id" not in data or "confirmation" not in data:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Missing 'task_id' or 'confirmation' in request"
            })
        }
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "status": "override_accepted",
            "task_id": data["task_id"],
            "message": "Gate decision overridden. Proceed with caution."
        })
    }
