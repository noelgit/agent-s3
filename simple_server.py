#!/usr/bin/env python3
"""
Ultra-simple WebSocket server for Agent-S3 connection testing.
"""
import socket
import threading
import json
import time
import os
import hashlib
import base64
import struct

HOST = "127.0.0.1"
PORT = 8765
AUTH_TOKEN = "agent-s3-token-2025"

def create_connection_file():
    """Create connection file for VS Code extension."""
    config = {
        "host": "localhost",
        "port": PORT,
        "auth_token": AUTH_TOKEN,
        "protocol": "ws",
        "version": "1.0.0"
    }
    
    with open(".agent_s3_ws_connection.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Created connection file: {os.path.abspath('.agent_s3_ws_connection.json')}")

def websocket_handshake(client_socket, request):
    """Perform WebSocket handshake."""
    lines = request.decode().split('\r\n')
    key = None
    
    for line in lines:
        if line.startswith('Sec-WebSocket-Key:'):
            key = line.split(': ')[1]
            break
    
    if not key:
        return False
    
    # WebSocket handshake response
    accept_key = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode()
    
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n"
        "\r\n"
    )
    
    client_socket.send(response.encode())
    return True

def decode_websocket_frame(data):
    """Decode a WebSocket frame."""
    if len(data) < 2:
        return None
    
    byte1, byte2 = struct.unpack('!BB', data[:2])
    
    fin = (byte1 >> 7) & 1
    opcode = byte1 & 0x0f
    masked = (byte2 >> 7) & 1
    payload_length = byte2 & 0x7f
    
    offset = 2
    
    if payload_length == 126:
        payload_length = struct.unpack('!H', data[offset:offset+2])[0]
        offset += 2
    elif payload_length == 127:
        payload_length = struct.unpack('!Q', data[offset:offset+8])[0]
        offset += 8
    
    if masked:
        mask = data[offset:offset+4]
        offset += 4
        payload = bytearray(data[offset:offset+payload_length])
        for i in range(payload_length):
            payload[i] ^= mask[i % 4]
    else:
        payload = data[offset:offset+payload_length]
    
    return payload.decode('utf-8') if payload else None

def encode_websocket_frame(message):
    """Encode a message as a WebSocket frame."""
    message_bytes = message.encode('utf-8')
    length = len(message_bytes)
    
    if length < 126:
        frame = struct.pack('!BB', 0x81, length)
    elif length < 65536:
        frame = struct.pack('!BBH', 0x81, 126, length)
    else:
        frame = struct.pack('!BBQ', 0x81, 127, length)
    
    return frame + message_bytes

def handle_client(client_socket, addr):
    """Handle individual client connection."""
    print(f"🔌 New connection from {addr}")
    authenticated = False
    
    try:
        # Receive handshake request
        request = client_socket.recv(4096)
        if not websocket_handshake(client_socket, request):
            print(f"❌ Handshake failed for {addr}")
            return
        
        print(f"✅ WebSocket handshake completed for {addr}")
        
        while True:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                message_text = decode_websocket_frame(data)
                if not message_text:
                    continue
                
                try:
                    message = json.loads(message_text)
                    msg_type = message.get("type")
                    content = message.get("content", {})
                    
                    print(f"📨 Received: {msg_type}")
                    
                    if msg_type == "auth":
                        token = content.get("token")
                        if token == AUTH_TOKEN:
                            authenticated = True
                            response = {
                                "type": "connection_established",
                                "content": {"message": "Authentication successful"}
                            }
                            print(f"🔐 Client {addr} authenticated")
                        else:
                            response = {
                                "type": "auth_failed",
                                "content": {"message": "Invalid token"}
                            }
                            print(f"🚫 Authentication failed for {addr}")
                    
                    elif authenticated and msg_type == "command":
                        command = content.get("command", "")
                        request_id = content.get("request_id", "")
                        
                        if command == "/help":
                            result = """🤖 Agent-S3 Help

Available commands:
• /help - Show this help
• /status - Server status  
• /ping - Test connection

✅ WebSocket connection is working!
🚀 Agent-S3 is ready to assist you."""
                        
                        elif command == "/status":
                            result = f"""📊 Server Status

🟢 Status: Running
🌐 Host: {HOST}
🔌 Port: {PORT}
⏰ Uptime: Active
✅ Connection: Established

All systems operational! 🎉"""
                        
                        elif command == "/ping":
                            result = "🏓 Pong! Connection test successful! ✅"
                        
                        else:
                            result = f"""📝 Command Received: {command}

🔄 Processing your request...
✅ WebSocket communication is working!
🤖 Agent-S3 is ready for action!"""
                        
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": result
                            }
                        }
                        print(f"⚡ Processed command: {command}")
                    
                    else:
                        response = {
                            "type": "auth_required",
                            "content": {"message": "Authentication required"}
                        }
                    
                    # Send response
                    response_json = json.dumps(response)
                    frame = encode_websocket_frame(response_json)
                    client_socket.send(frame)
                    
                except json.JSONDecodeError:
                    print(f"⚠️  Invalid JSON from {addr}")
                
            except Exception as e:
                print(f"❌ Error handling message from {addr}: {e}")
                break
                
    except Exception as e:
        print(f"❌ Connection error with {addr}: {e}")
    finally:
        client_socket.close()
        print(f"🔌 Connection closed for {addr}")

def main():
    """Start the simple WebSocket server."""
    create_connection_file()
    
    # Create socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        
        print("🚀 Agent-S3 Simple WebSocket Server")
        print("=" * 50)
        print(f"🌐 Listening on {HOST}:{PORT}")
        print(f"🔑 Auth token: {AUTH_TOKEN}")
        print(f"📁 Connection file: .agent_s3_ws_connection.json")
        print("=" * 50)
        print("✅ Server ready! Waiting for connections...")
        print("Press Ctrl+C to stop")
        
        while True:
            client_socket, addr = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, addr)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
    finally:
        server_socket.close()
        try:
            os.remove(".agent_s3_ws_connection.json")
            print("🗑️  Removed connection file")
        except:
            pass

if __name__ == "__main__":
    main()
