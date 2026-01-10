"""Health check endpoint - lightweight, no heavy dependencies."""

from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "service": "MPRG - Multi-Path Reasoning Guard",
            "status": "running",
            "endpoints": [
                "POST /api/analyze - Run MPRG analysis",
                "GET /api/history - Get recent analyses",
                "GET /api/task?id=<id> - Get specific task analysis",
                "POST /api/override - Override gate decision",
                "GET /api/patterns - Get fragile patterns"
            ]
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
