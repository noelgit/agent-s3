import time
import socket
import requests
from agent_s3.communication.http_server import EnhancedHTTPServer


def get_free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(mount_path=""):
    port = get_free_port()
    server = EnhancedHTTPServer(host="localhost", port=port, mount_path=mount_path)
    thread = server.start_in_thread()
    time.sleep(0.2)
    return server, port


def stop_server(server):
    server.stop_sync()


def test_mount_path_with_trailing_slash_redirect():
    server, port = start_server("/api/")
    try:
        resp = requests.get(f"http://localhost:{port}/api", allow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["Location"].endswith("/api/")
        resp = requests.get(f"http://localhost:{port}/api/health")
        assert resp.status_code == 200
    finally:
        stop_server(server)


def test_mount_path_without_trailing_slash():
    server, port = start_server("/api")
    try:
        resp = requests.get(f"http://localhost:{port}/api/health")
        assert resp.status_code == 200
    finally:
        stop_server(server)
