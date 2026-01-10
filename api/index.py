"""Health check endpoint - lightweight, no heavy dependencies."""

import json


def handler(request):
    """Vercel Python serverless function handler."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "service": "MPRG - Multi-Path Reasoning Guard",
            "status": "running",
            "endpoints": [
                "POST /api/analyze - Run MPRG analysis",
                "GET /api/history - Get recent analyses",
                "GET /api/task?id=<id> - Get specific task analysis",
                "POST /api/override - Override gate decision",
                "GET /api/patterns - Get fragile patterns"
            ]
        })
    }
