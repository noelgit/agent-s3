"""Tests for the TechStackDetector component."""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.tech_stack_detector import TechStackDetector

class TestTechStackDetector:
    """Tests for the TechStackDetector class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        return config
    
    @pytest.fixture
    def mock_file_tool(self):
        """Create a mock file tool."""
        file_tool = MagicMock()
        return file_tool
    
    @pytest.fixture
    def mock_scratchpad(self):
        """Create a mock scratchpad."""
        scratchpad = MagicMock()
        scratchpad.log = MagicMock()
        return scratchpad
    
    @pytest.fixture
    def mock_tech_stack_manager(self):
        """Create a mock TechStackManager."""
        tech_stack_manager = MagicMock()
        
        # Mock detect_tech_stack method
        tech_stack_manager.detect_tech_stack.return_value = {
            "languages": [{"name": "Python", "version": "3.10"}],
            "frameworks": [{"name": "Flask", "version": "2.0.1"}],
            "libraries": [{"name": "SQLAlchemy", "version": "1.4.0"}],
            "tools": [{"name": "pytest", "version": "7.0.0"}],
            "versions": {"python": "3.10", "flask": "2.0.1"},
            "meta": {"has_requirements_txt": True}
        }
        
        # Mock get_structured_tech_stack method
        tech_stack_manager.get_structured_tech_stack.return_value = {
            "languages": [{"name": "Python", "version": "3.10"}],
            "frameworks": [{"name": "Flask", "version": "2.0.1"}],
            "libraries": [{"name": "SQLAlchemy", "version": "1.4.0"}],
            "tools": [{"name": "pytest", "version": "7.0.0"}],
            "versions": {"python": "3.10", "flask": "2.0.1"},
            "meta": {"has_requirements_txt": True}
        }
        
        # Mock get_formatted_tech_stack method
        tech_stack_manager.get_formatted_tech_stack.return_value = """# Tech Stack
- Python 3.10
- Flask 2.0.1
- SQLAlchemy 1.4.0
- pytest 7.0.0"""
        
        return tech_stack_manager
    
    @pytest.fixture
    def tech_stack_detector(self, mock_config, mock_file_tool, mock_scratchpad):
        """Create a TechStackDetector instance with mocks."""
        return TechStackDetector(
            config=mock_config,
            file_tool=mock_file_tool,
            scratchpad=mock_scratchpad
        )
    
    @patch('agent_s3.tools.tech_stack_manager.TechStackManager')
    def test_detect_tech_stack(self, mock_tech_stack_manager_class, tech_stack_detector, mock_tech_stack_manager):
        """Test detect_tech_stack method."""
        # Setup
        mock_tech_stack_manager_class.return_value = mock_tech_stack_manager
        
        # Exercise
        result = tech_stack_detector.detect_tech_stack()
        
        # Verify
        mock_tech_stack_manager_class.assert_called_once()
        mock_tech_stack_manager.detect_tech_stack.assert_called_once()
        assert "languages" in result
        assert "frameworks" in result
        assert "libraries" in result
        assert len(result["languages"]) == 1
        assert result["languages"][0]["name"] == "Python"
    
    @patch('agent_s3.tools.tech_stack_manager.TechStackManager')
    def test_get_structured_tech_stack(self, mock_tech_stack_manager_class, tech_stack_detector, mock_tech_stack_manager):
        """Test get_structured_tech_stack method."""
        # Setup
        mock_tech_stack_manager_class.return_value = mock_tech_stack_manager
        tech_stack_detector.tech_stack_manager = mock_tech_stack_manager
        
        # Exercise
        result = tech_stack_detector.get_structured_tech_stack()
        
        # Verify
        mock_tech_stack_manager.get_structured_tech_stack.assert_called_once()
        assert "languages" in result
        assert "frameworks" in result
        assert "libraries" in result
        assert "versions" in result
        assert result["versions"]["python"] == "3.10"
    
    @patch('agent_s3.tools.tech_stack_manager.TechStackManager')
    def test_get_formatted_tech_stack(self, mock_tech_stack_manager_class, tech_stack_detector, mock_tech_stack_manager):
        """Test get_formatted_tech_stack method."""
        # Setup
        mock_tech_stack_manager_class.return_value = mock_tech_stack_manager
        tech_stack_detector.tech_stack_manager = mock_tech_stack_manager
        
        # Exercise
        result = tech_stack_detector.get_formatted_tech_stack()
        
        # Verify
        mock_tech_stack_manager.get_formatted_tech_stack.assert_called_once()
        assert "Python" in result
        assert "Flask" in result
        assert "Tech Stack" in result
    
    def test_get_formatted_tech_stack_fallback(self, tech_stack_detector):
        """Test fallback implementation of get_formatted_tech_stack."""
        # Setup
        tech_stack_detector.tech_stack_manager = None
        tech_stack_detector._detected_stack = {
            "languages": [{"name": "Python", "version": "3.10"}],
            "frameworks": [{"name": "Flask", "version": "2.0.1"}],
            "libraries": [],
            "tools": [],
            "versions": {},
            "meta": {}
        }
        
        # Exercise
        result = tech_stack_detector.get_formatted_tech_stack()
        
        # Verify
        assert "Languages" in result
        assert "Python" in result
        assert "Frameworks" in result
        assert "Flask" in result
    
    @patch('agent_s3.tools.tech_stack_manager.TechStackManager')
    def test_detect_tech_stack_error(self, mock_tech_stack_manager_class, tech_stack_detector, mock_scratchpad):
        """Test error handling in detect_tech_stack."""
        # Setup
        mock_tech_stack_manager_class.side_effect = Exception("Test error")
        
        # Exercise
        result = tech_stack_detector.detect_tech_stack()
        
        # Verify
        mock_scratchpad.log.assert_called_with("TechStackDetector", "Error detecting tech stack: Test error", level="error")
        assert "languages" in result
        assert len(result["languages"]) == 0
        assert "frameworks" in result
        assert len(result["frameworks"]) == 0