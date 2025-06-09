from agent_s3.design_manager import DesignManager

def test_detect_design_completion_case_insensitive():
    """Design completion detection should handle mixed-case indicators."""
    manager = DesignManager()
    manager.conversation_history = [
        {"role": "system", "content": "init"},
        {"role": "user", "content": "List features"},
        {"role": "assistant", "content": "feature 1: login system"},
        {"role": "user", "content": "Looks Good"},
    ]

    assert manager.detect_design_completion()


def test_extract_features_from_conversation_includes_user_features():
    """Features from both assistant and user messages should be extracted without duplicates."""
    manager = DesignManager()
    manager.conversation_history = [
        {"role": "assistant", "content": "1. Login system"},
        {"role": "user", "content": "2. Search feature\n3. Profile"},
        {"role": "assistant", "content": "Feature 2: Search feature"},
    ]

    features = manager._extract_features_from_conversation()

    assert features == ["Login system", "Search feature", "Profile"]
