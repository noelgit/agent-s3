"""
Stub for VSCodeIntegration to allow tests to import and run.
"""

class VSCodeIntegration:
    def __init__(self, port=None):
        self.is_running = True
        self.connect_file_path = "/tmp/vscode_integration_test.sock"
        self.server_thread = self
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.is_running = False
    def is_alive(self):
        return False
