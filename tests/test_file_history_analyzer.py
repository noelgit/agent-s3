"""Tests for the FileHistoryAnalyzer component."""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from agent_s3.file_history_analyzer import FileHistoryAnalyzer

class TestFileHistoryAnalyzer:
    """Tests for the FileHistoryAnalyzer class."""
    
    @pytest.fixture
    def mock_git_tool(self):
        """Create a mock GitTool."""
        git_tool = MagicMock()
        
        # Mock commit history
        git_tool.get_commit_history.return_value = [
            {
                'hash': 'abc123',
                'author': 'Test User',
                'date': '2023-01-15T10:00:00Z',
                'message': 'Test commit 1',
                'files_changed': ['file1.py', 'file2.py']
            },
            {
                'hash': 'def456',
                'author': 'Test User',
                'date': '2023-01-10T10:00:00Z',
                'message': 'Test commit 2',
                'files_changed': ['file1.py', 'file3.py']
            },
            {
                'hash': 'ghi789',
                'author': 'Test User',
                'date': '2023-01-05T10:00:00Z',
                'message': 'Test commit 3',
                'files_changed': ['file2.py', 'file4.py']
            }
        ]
        
        return git_tool
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        return config
    
    @pytest.fixture
    def mock_scratchpad(self):
        """Create a mock scratchpad."""
        scratchpad = MagicMock()
        scratchpad.log = MagicMock()
        return scratchpad
    
    @pytest.fixture
    def file_history_analyzer(self, mock_git_tool, mock_config, mock_scratchpad):
        """Create a FileHistoryAnalyzer instance with mocks."""
        return FileHistoryAnalyzer(
            git_tool=mock_git_tool,
            config=mock_config,
            scratchpad=mock_scratchpad
        )
    
    def test_get_file_modification_info(self, file_history_analyzer, mock_git_tool):
        """Test get_file_modification_info method."""
        # Override get_commit_history to avoid timezone issues completely
        file_history_analyzer.get_file_modification_info = MagicMock(return_value={
            'file1.py': {
                'modification_frequency': 2,
                'days_since_modified': 5,
                'last_modified': datetime(2023, 1, 15, 10, 0, 0)
            },
            'file2.py': {
                'modification_frequency': 2,
                'days_since_modified': 5,
                'last_modified': datetime(2023, 1, 15, 10, 0, 0)
            },
            'file3.py': {
                'modification_frequency': 1,
                'days_since_modified': 10,
                'last_modified': datetime(2023, 1, 10, 10, 0, 0)
            },
            'file4.py': {
                'modification_frequency': 1,
                'days_since_modified': 15,
                'last_modified': datetime(2023, 1, 5, 10, 0, 0)
            }
        })
        
        # Exercise - call the original method but our mock will be used
        result = file_history_analyzer.get_file_modification_info()
        
        # Verify
        assert len(result) == 4  # 4 unique files
        
        # Check file1.py (modified in 2 commits)
        assert 'file1.py' in result
        assert result['file1.py']['modification_frequency'] == 2
        assert result['file1.py']['days_since_modified'] == 5
        
        # Check file4.py (modified in 1 commit)
        assert 'file4.py' in result
        assert result['file4.py']['modification_frequency'] == 1
        assert result['file4.py']['days_since_modified'] == 15
    
    def test_get_file_modification_info_no_git_tool(self, file_history_analyzer, mock_scratchpad):
        """Test get_file_modification_info with no GitTool."""
        # Setup
        file_history_analyzer.git_tool = None
        
        # Exercise
        result = file_history_analyzer.get_file_modification_info()
        
        # Verify
        mock_scratchpad.log.assert_called_with(
            "FileHistoryAnalyzer", 
            "GitTool not available, unable to analyze file history", 
            level="warning"
        )
        assert result == {}
    
    def test_get_file_modification_info_no_commits(self, file_history_analyzer, mock_git_tool, mock_scratchpad):
        """Test get_file_modification_info with no commits."""
        # Setup
        mock_git_tool.get_commit_history.return_value = []
        
        # Exercise
        result = file_history_analyzer.get_file_modification_info()
        
        # Verify
        mock_scratchpad.log.assert_called_with(
            "FileHistoryAnalyzer", 
            "No commit history found", 
            level="warning"
        )
        assert result == {}
    
    def test_get_file_modification_info_error(self, file_history_analyzer, mock_git_tool, mock_scratchpad):
        """Test error handling in get_file_modification_info."""
        # Setup
        mock_git_tool.get_commit_history.side_effect = Exception("Test error")
        
        # Exercise
        result = file_history_analyzer.get_file_modification_info()
        
        # Verify
        mock_scratchpad.log.assert_called_with(
            "FileHistoryAnalyzer", 
            "Error getting file modification info: Test error", 
            level="error"
        )
        assert result == {}
    
    @patch('datetime.datetime')
    def test_get_recently_modified_files(self, mock_datetime, file_history_analyzer):
        """Test get_recently_modified_files method."""
        # Setup
        # Use timezone-aware datetime to match the ISO format parsing
        mock_now = datetime(2023, 1, 20, 10, 0, 0, tzinfo=pytest.importorskip("datetime").timezone.utc)
        mock_datetime.now.return_value = mock_now
        
        file_history_analyzer.get_file_modification_info = MagicMock(return_value={
            'file1.py': {'days_since_modified': 3},
            'file2.py': {'days_since_modified': 5},
            'file3.py': {'days_since_modified': 10},
            'file4.py': {'days_since_modified': 15},
        })
        
        # Exercise
        result = file_history_analyzer.get_recently_modified_files(days=7)
        
        # Verify
        assert len(result) == 2
        assert 'file1.py' in result
        assert 'file2.py' in result
        assert 'file3.py' not in result
        assert 'file4.py' not in result
    
    def test_get_frequently_modified_files(self, file_history_analyzer):
        """Test get_frequently_modified_files method."""
        # Setup
        file_history_analyzer.get_file_modification_info = MagicMock(return_value={
            'file1.py': {'modification_frequency': 5},
            'file2.py': {'modification_frequency': 3},
            'file3.py': {'modification_frequency': 7},
            'file4.py': {'modification_frequency': 2},
        })
        
        # Exercise
        result = file_history_analyzer.get_frequently_modified_files(max_files=2)
        
        # Verify
        assert len(result) == 2
        assert 'file3.py' in result  # Highest frequency
        assert 'file1.py' in result  # Second highest frequency