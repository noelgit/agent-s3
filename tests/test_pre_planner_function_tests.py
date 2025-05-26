"""Tests for function-level test requirements in pre_planner_json_enforced."""
import pytest
from unittest.mock import MagicMock

import agent_s3.pre_planner_json_enforced as pre_planner
from agent_s3.router_agent import RouterAgent


@pytest.fixture
def router_agent():
    """Create a mocked router agent."""
    mock_router = MagicMock(spec=RouterAgent)
    mock_router.call_llm_by_role.return_value = '{"example_key": "example_value"}'
    return mock_router


@pytest.fixture
def mock_context():
    """Create a mock context with necessary components."""
    return {
        "file_tool": MagicMock(),
        "code_analysis_tool": MagicMock(),
        "tech_stack": {"languages": ["python", "javascript"]},
        "project_structure": "Mock project structure"
    }


@pytest.fixture
def sample_python_function():
    """Return a sample Python function content."""
    return """
def calculate_total(items: list, tax_rate: float = 0.1) -> float:
    \"\"\"
    Calculate the total price with tax for a list of items.

    Args:
        items: List of items with their prices
        tax_rate: The tax rate to apply (default: 0.1)

    Returns:
        The total price including tax
    \"\"\"
    subtotal = sum(item.get('price', 0) for item in items)
    return subtotal * (1 + tax_rate)
"""


@pytest.fixture
def sample_js_function():
    """Return a sample JavaScript function content."""
    return """
/**
 * Calculate the total price with tax for a list of items.
 * @param {Array} items - List of items with their prices
 * @param {number} taxRate - The tax rate to apply (default: 0.1)
 * @returns {number} The total price including tax
 */
function calculateTotal(items, taxRate = 0.1) {
    const subtotal = items.reduce((sum, item) => sum + (item.price || 0), 0);
    return subtotal * (1 + taxRate);
}
"""


@pytest.fixture
def sample_class_with_methods():
    """Return a sample Python class with methods."""
    return """
class ShoppingCart:
    \"\"\"
    A shopping cart that holds items and calculates totals.
    \"\"\"

    def __init__(self, customer_id: str, tax_rate: float = 0.1):
        \"\"\"
        Initialize a shopping cart.

        Args:
            customer_id: Unique identifier for the customer
            tax_rate: The tax rate to apply to the cart
        \"\"\"
        self.customer_id = customer_id
        self.items = []
        self.tax_rate = tax_rate

    def add_item(self, item_id: str, name: str, price: float, quantity: int = 1) -> None:
        \"\"\"
        Add an item to the cart.

        Args:
            item_id: Unique identifier for the item
            name: Name of the item
            price: Price of a single item
            quantity: Number of items to add
        \"\"\"
        self.items.append({
            'id': item_id,
            'name': name,
            'price': price,
            'quantity': quantity
        })

    def remove_item(self, item_id: str) -> bool:
        \"\"\"
        Remove an item from the cart.

        Args:
            item_id: ID of the item to remove

        Returns:
            True if item was removed, False if not found
        \"\"\"
        initial_count = len(self.items)
        self.items = [item for item in self.items if item['id'] != item_id]
        return len(self.items) < initial_count

    async def calculate_total(self) -> float:
        \"\"\"
        Calculate the total price of all items with tax.

        Returns:
            The total price including tax
        \"\"\"
        subtotal = sum(item['price'] * item['quantity'] for item in self.items)
        return subtotal * (1 + self.tax_rate)
"""


@pytest.fixture
def temp_python_file(tmp_path, sample_python_function):
    """Create a temporary Python file with a sample function."""
    file_path = tmp_path / "calculator.py"
    file_path.write_text(sample_python_function)
    return file_path


@pytest.fixture
def temp_js_file(tmp_path, sample_js_function):
    """Create a temporary JavaScript file with a sample function."""
    file_path = tmp_path / "calculator.js"
    file_path.write_text(sample_js_function)
    return file_path


@pytest.fixture
def temp_class_file(tmp_path, sample_class_with_methods):
    """Create a temporary Python file with a sample class."""
    file_path = tmp_path / "shopping_cart.py"
    file_path.write_text(sample_class_with_methods)
    return file_path


def test_call_pre_planner_with_enforced_json(router_agent, mock_context):
    """Test that pre_planning_workflow returns valid data."""
    # Mock the router agent's call_llm_by_role to return a valid JSON
    router_agent.call_llm_by_role.return_value = """
    {
        "original_request": "Create a calculator",
        "feature_groups": [
            {
                "group_name": "Basic Calculations",
                "group_description": "Core arithmetic operations",
                "features": [
                    {
                        "name": "Addition",
                        "description": "Add two numbers",
                        "files_affected": ["calculator.py"],
                        "test_requirements": {
                            "unit": ["Test with positive numbers"],
                            "integration": [],
                            "property_based": [],
                            "acceptance": [],
                            "approval_baseline": [],
                            "mockup_strategy": "Manual testing with sample inputs",
                            "target_coverage": "90%"
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": []
                        },
                        "system_design": "Implementation details"
                    }
                ]
            }
        ]
    }
    """
    # Call function
    from agent_s3.pre_planner_json_enforced import pre_planning_workflow
    success, result = pre_planning_workflow(
        router_agent, "Create a calculator", context=mock_context
    )
    # Verify success
    assert success
    assert isinstance(result, dict)
    assert "original_request" in result
    assert "feature_groups" in result
    assert len(result["feature_groups"]) > 0
    # Ensure context was included in the prompt
    _, call_kwargs = router_agent.call_llm_by_role.call_args
    assert "Context:" in call_kwargs.get("user_prompt", "")


def test_regenerate_pre_planning_with_modifications(router_agent):
    """Test regenerating pre-planning results with modifications."""
    # Original results
    original_results = {
        "original_request": "Create a calculator",
        "feature_groups": [
            {
                "group_name": "Basic Calculations",
                "group_description": "Core arithmetic operations",
                "features": [
                    {
                        "name": "Addition",
                        "description": "Add two numbers",
                        "files_affected": ["calculator.py"],
                        "test_requirements": {
                            "unit_tests": [
                                {
                                    "description": "Test with positive numbers",
                                    "target_element": "add",
                                    "target_element_id": "addition_function",
                                    "inputs": ["1", "2"],
                                    "expected_outcome": "Returns 3"
                                }
                            ],
                            "integration_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": []
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": [],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        },
                        "system_design": "Implementation details"
                    }
                ]
            }
        ]
    }

    # Modification text
    modification_text = "Add subtraction feature"

    # Mock router agent response
    router_agent.call_llm_by_role.return_value = """
    {
        "original_request": "Create a calculator",
        "feature_groups": [
            {
                "group_name": "Basic Calculations",
                "group_description": "Core arithmetic operations",
                "features": [
                    {
                        "name": "Addition",
                        "description": "Add two numbers",
                        "files_affected": ["calculator.py"],
                        "test_requirements": {
                            "unit": ["Test with positive numbers"],
                            "integration": [],
                            "property_based": [],
                            "acceptance": [],
                            "approval_baseline": [],
                            "mockup_strategy": "Manual testing with sample inputs",
                            "target_coverage": "90%"
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": [],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        },
                        "system_design": "Implementation details"
                    },
                    {
                        "name": "Subtraction",
                        "description": "Subtract one number from another",
                        "files_affected": ["calculator.py"],
                        "test_requirements": {
                            "unit": ["Test with positive numbers", "Test with negative numbers"],
                            "integration": [],
                            "property_based": [],
                            "acceptance": [],
                            "approval_baseline": [],
                            "mockup_strategy": "Manual testing with sample inputs",
                            "target_coverage": "90%"
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": [],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        },
                        "system_design": "Implementation details for subtraction"
                    }
                ]
            }
        ]
    }
    """

    # Call function
    result = pre_planner.regenerate_pre_planning_with_modifications(
        router_agent, original_results, modification_text
    )

    # Verify new feature was added
    assert isinstance(result, dict)
    assert "feature_groups" in result
    assert len(result["feature_groups"]) > 0

    # Check if subtraction feature was added
    features = result["feature_groups"][0]["features"]
    feature_names = [f["name"] for f in features]
    assert "Subtraction" in feature_names


def test_process_response_with_valid_json():
    """Test processing a valid JSON response."""
    # Valid JSON response
    response = """
    {
        "original_request": "Create a calculator",
        "feature_groups": [
            {
                "group_name": "Basic Calculations",
                "group_description": "Core arithmetic operations",
                "features": [
                    {
                        "name": "Addition",
                        "description": "Add two numbers",
                        "files_affected": ["calculator.py"],
                        "test_requirements": {
                            "unit": ["Test with positive numbers"],
                            "integration": [],
                            "property_based": [],
                            "acceptance": [],
                            "approval_baseline": [],
                            "mockup_strategy": "Manual testing with sample inputs",
                            "target_coverage": "90%"
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": [],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        },
                        "system_design": "Implementation details"
                    }
                ]
            }
        ]
    }
    """

    # Call process_response
    success, result = pre_planner.process_response(response, "Create a calculator")

    # Verify success
    assert success
    assert isinstance(result, dict)
    assert "original_request" in result
    assert "feature_groups" in result


def test_process_response_with_invalid_json():
    """Test processing an invalid JSON response and getting a fallback."""
    # Invalid JSON response
    response = """
    {
        "original_request": "Create a calculator",
        "feature_groups": [
            {
                "group_name": "Basic Calculations",
                "group_description": "Core arithmetic operations",
                "features": [
                    {
                        "name": "Addition",
                        "description": "Add two numbers",
    """

    # Call process_response
    success, result = pre_planner.process_response(response, "Create a calculator")

    # Verify fallback was used
    assert success is False
    assert result is None


def test_create_fallback_json():
    """Test creation of fallback JSON."""
    # Call create_fallback_json
    fallback = pre_planner.create_fallback_json("Create a calculator")

    # Verify fallback structure
    assert isinstance(fallback, dict)
    assert "original_request" in fallback
    assert fallback["original_request"] == "Create a calculator"
    assert "feature_groups" in fallback
    assert len(fallback["feature_groups"]) > 0
    assert "features" in fallback["feature_groups"][0]
    assert len(fallback["feature_groups"][0]["features"]) > 0
    valid, msg = pre_planner.validate_preplan_all(fallback)
    assert valid, msg


def test_clarification_callback_invoked_when_disabled(monkeypatch, router_agent):
    """Ensure callback is used when interactive clarification is disabled."""

    router_agent.call_llm_by_role.side_effect = [
        '{"question": "Need more details?"}',
        '{"original_request": "task", "feature_groups": []}',
    ]

    captured = {}

    def callback(question: str) -> str:
        captured["question"] = question
        return "answer"

    input_called = False

    def fake_input(prompt: str = "") -> str:
        nonlocal input_called
        input_called = True
        return "ignored"

    monkeypatch.setattr("builtins.input", fake_input)

    import agent_s3.pre_planner_json_enforced as pre_planner
    monkeypatch.setattr(pre_planner, "validate_json_schema", lambda data: (True, ""))
    from agent_s3.pre_planner_json_enforced import pre_planning_workflow

    success, result = pre_planning_workflow(
        router_agent,
        "task",
        allow_interactive_clarification=False,
        clarification_callback=callback,
    )

    assert success
    assert captured["question"] == "Need more details?"
    assert not input_called
