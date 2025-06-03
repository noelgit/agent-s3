#!/usr/bin/env python3
"""Simple HTTP server alternative to WebSocket"""

import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))


class Agent3Handler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/health':
            self.send_json({'status': 'ok'})
        elif parsed.path == '/help':
            result = self.execute_command('/help')
            self.send_json({'result': result})
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                command = data.get('command', '')
                result = self.execute_command(command)
                self.send_json({'result': result})
            except Exception as e:
                self.send_json({'error': str(e)}, status=500)
        else:
            self.send_error(404)
    
    def execute_command(self, command):
        """Execute Agent-S3 command"""
        try:
            # Simple command mapping
            if command == '/help':
                return """Available commands:
/help - Show this help
/init - Initialize workspace  
/plan <description> - Generate a plan
/test - Run tests
/config - Show configuration"""
            
            elif command == '/config':
                return "Agent-S3 Configuration: Ready"
            
            elif command.startswith('/plan'):
                description = command.replace('/plan', '').strip()
                return f"Plan for: {description}\n1. Analyze requirements\n2. Design solution\n3. Implement\n4. Test"
            
            else:
                return f"Unknown command: {command}"
                
        except Exception as e:
            return f"Error: {str(e)}"
    
    def send_json(self, data, status=200):
        """Send JSON response"""
        response = json.dumps(data).encode('utf-8')
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        self.wfile.write(response)
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def main():
    """Start the HTTP server"""
    port = 8081  # Different port to avoid conflicts
    
    # Write connection info for VS Code
    connection_info = {
        "type": "http",
        "host": "localhost", 
        "port": port,
        "base_url": f"http://localhost:{port}"
    }
    
    with open('.agent_s3_http_connection.json', 'w') as f:
        json.dump(connection_info, f)
    
    print(f"Starting Agent-S3 HTTP server on http://localhost:{port}")
    print("Available endpoints:")
    print("  GET  /health")
    print("  GET  /help") 
    print("  POST /command")
    print("\nPress Ctrl+C to stop")
    
    httpd = HTTPServer(('localhost', port), Agent3Handler)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()

if __name__ == "__main__":
    main()