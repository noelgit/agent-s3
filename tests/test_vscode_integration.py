import os
import socket
import unittest

from agent_s3.vscode_integration import VSCodeIntegration

def get_free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestVSCodeIntegrationShutdown(unittest.TestCase):
    """Verify VSCodeIntegration cleans up resources on shutdown."""

    def test_server_thread_and_connection_file_cleanup(self):
        port = get_free_port()
        os.environ["VSCODE_AUTH_TOKEN"] = "test-token"
        with VSCodeIntegration(port=port) as integration:
            self.assertTrue(integration.is_running)
            self.assertTrue(os.path.exists(integration.connect_file_path))
            if os.name == "posix":
                import stat
                mode = stat.S_IMODE(os.stat(integration.connect_file_path).st_mode)
                self.assertEqual(mode, 0o600)
            server_thread = integration.server_thread
        # Context exit should stop server
        self.assertFalse(server_thread.is_alive())
        self.assertFalse(os.path.exists(integration.connect_file_path))


if __name__ == "__main__":
    unittest.main()
