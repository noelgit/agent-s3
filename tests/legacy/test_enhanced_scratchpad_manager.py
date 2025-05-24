import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import unittest

from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
from agent_s3.config import Config


class TestEnhancedScratchpadManager(unittest.TestCase):
    """Tests for EnhancedScratchpadManager utilities."""

    def test_cleanup_old_sessions(self):
        """Ensure cleanup skips malformed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)

            # Valid log files for two sessions
            valid1 = logs_dir / "scratchpad_20210101_000000_part1.log"
            valid2 = logs_dir / "scratchpad_20210102_000000_part1.log"
            valid1.write_text("a")
            valid2.write_text("b")

            # File that does not match expected pattern
            (logs_dir / "scratchpad_invalid.log").write_text("bad")

            # Symlink pointing outside log directory
            outside_file = Path(tmpdir).parent / "outside.log"
            outside_file.write_text("mal")
            malicious = logs_dir / "scratchpad_20210103_000000_part1.log"
            malicious.symlink_to(outside_file)

            cfg = MagicMock(spec=Config)
            cfg.config = {
                "scratchpad_max_sessions": 1,
                "scratchpad_log_dir": logs_dir.as_posix(),
                "scratchpad_enable_encryption": False,
                "scratchpad_max_file_size_mb": 1,
            }

            with patch("os.remove") as mock_remove:
                manager = EnhancedScratchpadManager(cfg)
                manager.logger = MagicMock()

                # Reset mock after initialization cleanup
                mock_remove.reset_mock()

                manager._cleanup_old_sessions()

                removed = {Path(c.args[0]) for c in mock_remove.call_args_list}
                self.assertIn(valid1.resolve(), removed)
                self.assertIn(valid2.resolve(), removed)
                self.assertNotIn(malicious.resolve(), removed)
                manager.logger.warning.assert_called_with(
                    "Skipping deletion of invalid file path: %s", malicious.as_posix()
                )

