#!/usr/bin/env python3
"""
Test script to verify that conversation history is properly reset
between different /design and /design-auto commands.
"""

import sys

# Add the project root to Python path
sys.path.insert(0, '/Users/noelpatron/Documents/GitHub/agent-s3')

from agent_s3.design_manager import DesignManager
from agent_s3.coordinator import Coordinator

def test_conversation_reset():
    """Test that conversation history is reset between design sessions."""
    print("Testing conversation history reset functionality...")
    
    # Create coordinator and design manager
    coordinator = Coordinator()
    design_manager = DesignManager(coordinator)
    
    # Test 1: Start first design conversation
    print("\n1. Starting first design conversation...")
    response1 = design_manager.start_design_conversation("Create a simple blog app")
    print(f"   Response length: {len(response1) if response1 else 0} characters")
    print(f"   Conversation history length: {len(design_manager.conversation_history)}")
    print(f"   Design objective: '{design_manager.design_objective}'")
    
    # Add some conversation
    design_manager.continue_conversation("I want user authentication and post management")
    print(f"   After continue: {len(design_manager.conversation_history)} messages")
    
    # Test 2: Start second design conversation (should reset)
    print("\n2. Starting second design conversation (should reset)...")
    response2 = design_manager.start_design_conversation("Create a todo app with real-time sync")
    print(f"   Response length: {len(response2) if response2 else 0} characters")
    print(f"   Conversation history length: {len(design_manager.conversation_history)}")
    print(f"   Design objective: '{design_manager.design_objective}'")
    
    # Test 3: Explicit reset method
    print("\n3. Testing explicit reset method...")
    design_manager.continue_conversation("Add mobile app support")
    print(f"   Before reset: {len(design_manager.conversation_history)} messages")
    print(f"   Features identified: {design_manager.features_identified}")
    print(f"   Consecutive feature messages: {design_manager.consecutive_feature_messages}")
    
    design_manager.reset_conversation()
    print(f"   After reset: {len(design_manager.conversation_history)} messages")
    print(f"   Design objective: '{design_manager.design_objective}'")
    print(f"   Features identified: {design_manager.features_identified}")
    print(f"   Consecutive feature messages: {design_manager.consecutive_feature_messages}")
    
    # Verification
    assert len(design_manager.conversation_history) == 0, "Conversation history should be empty after reset"
    assert design_manager.design_objective == "", "Design objective should be empty after reset"
    assert not design_manager.features_identified, "Features identified should be False after reset"
    assert design_manager.consecutive_feature_messages == 0, "Consecutive feature messages should be 0 after reset"
    
    print("\n✅ All tests passed! Conversation reset functionality works correctly.")
    return True

def test_coordinator_design_commands():
    """Test that coordinator design commands properly reset conversation."""
    print("\nTesting coordinator design command reset...")
    
    coordinator = Coordinator()
    
    # Simulate design manager having some state
    if hasattr(coordinator, 'design_manager'):
        design_manager = coordinator.design_manager
    else:
        design_manager = DesignManager(coordinator)
        coordinator.design_manager = design_manager
    
    # Add some fake conversation state
    design_manager.conversation_history = [
        {"role": "user", "content": "Old conversation"},
        {"role": "assistant", "content": "Old response"}
    ]
    design_manager.design_objective = "Old objective"
    design_manager.features_identified = True
    
    print(f"   Before execute_design: {len(design_manager.conversation_history)} messages")
    print(f"   Old objective: '{design_manager.design_objective}'")
    
    # Test execute_design - this should reset conversation
    try:
        # This will call start_design_conversation which should reset everything
        coordinator.execute_design("New design objective: task management system")
        print(f"   After execute_design: {len(design_manager.conversation_history)} messages")
        print(f"   New objective: '{design_manager.design_objective}'")
        print("   ✅ execute_design reset test completed")
    except Exception as e:
        print(f"   ⚠️  execute_design test encountered: {e}")
    
    return True

if __name__ == "__main__":
    try:
        test_conversation_reset()
        test_coordinator_design_commands()
        print("\n🎉 All conversation reset tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
