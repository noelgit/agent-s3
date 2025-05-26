"""Response parsing utilities for debugging system."""

import re
import json
from typing import Dict, Optional, Any


def extract_code_from_response(response: str) -> Optional[str]:
    """Extract code from a response."""
    # Look for code blocks with triple backticks
    pattern = r'```(?:\w*\n|\n)?(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        # Return the largest code block
        return max(matches, key=len)

    # No code blocks found, try to extract a file content section
    pattern = r'## Fix\s*\n(.*?)(?:\n##|\Z)'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        # Clean up any remaining markdown
        code = matches[0].strip()
        code = re.sub(r'^```\w*\s*', '', code)
        code = re.sub(r'```\s*$', '', code)
        return code

    return None


def extract_reasoning_from_response(response: str) -> str:
    """Extract reasoning from a response."""
    # Look for analysis or explanation sections

    # Try to find Analysis section
    analysis_pattern = r'(?:##\s*Analysis|Step-by-Step Analysis)\s*\n(.*?)(?:\n##|\Z)'
    analysis_matches = re.findall(analysis_pattern, response, re.DOTALL)

    # Try to find Explanation section
    explanation_pattern = r'(?:##\s*Explanation)\s*\n(.*?)(?:\n##|\Z)'
    explanation_matches = re.findall(explanation_pattern, response, re.DOTALL)

    # Try to find Root Cause section
    cause_pattern = r'(?:##\s*Root Cause)\s*\n(.*?)(?:\n##|\Z)'
    cause_matches = re.findall(cause_pattern, response, re.DOTALL)

    # Combine all found sections
    reasoning_parts = []

    if analysis_matches:
        reasoning_parts.append(analysis_matches[0].strip())

    if cause_matches:
        reasoning_parts.append(f"Root Cause: {cause_matches[0].strip()}")

    if explanation_matches:
        reasoning_parts.append(explanation_matches[0].strip())

    if reasoning_parts:
        return "\n\n".join(reasoning_parts)

    # If no structured sections found, return truncated response
    return response[:500] + ("..." if len(response) > 500 else "")


def extract_multi_file_fixes(response: str, fallback_file_path: Optional[str] = None) -> Dict[str, str]:
    """Extract multiple file fixes from a response."""
    fixes = {}

    # Look for file-specific code blocks with format ```filepath:/path/to/file
    pattern = r'```filepath:(.*?)\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        for file_path, content in matches:
            fixes[file_path.strip()] = content

    # If no structured file fixes found, try to extract a single code block
    if not fixes:
        code = extract_code_from_response(response)
        if code and fallback_file_path:
            fixes[fallback_file_path] = code

    return fixes


def extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a response."""
    # Try to find JSON content between code blocks
    pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass

    # Try to find JSON content without code blocks
    pattern = r'\{.*\}'
    matches = re.findall(pattern, response, re.DOTALL)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    return None


def extract_restart_strategy_from_response(response: str) -> Optional[str]:
    """Extract restart strategy from a response."""
    # Look for strategy section
    pattern = r'(?:##\s*Restart Strategy|Strategy)\s*:\s*(.*?)(?:\n##|\Z)'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

    # Look for bullet point strategy
    pattern = r'(?:Strategy|Approach)\s*:\s*\*\s*(.*?)(?:\n|$)'
    matches = re.findall(pattern, response)

    if matches:
        return matches[0].strip()

    return None


def extract_error_category_from_response(response: str) -> Optional[str]:
    """Extract error category from a response."""
    # Look for error category mentions
    categories = [
        'syntax_error', 'type_error', 'import_error', 'runtime_error',
        'test_failure', 'dependency_error', 'configuration_error'
    ]

    response_lower = response.lower()
    for category in categories:
        if category.replace('_', ' ') in response_lower or category in response_lower:
            return category

    return None


def extract_file_paths_from_response(response: str) -> list[str]:
    """Extract file paths mentioned in a response."""
    # Look for common file path patterns
    patterns = [
        r'`([^`]+\.py)`',  # Files in backticks
        r'filepath:\s*([^\s]+)',  # Explicit filepath declarations
        r'(?:file|path):\s*([^\s]+\.[a-z]+)',  # File declarations
        r'/[a-zA-Z0-9_/.-]+\.[a-z]+',  # Unix-style paths
    ]

    file_paths = set()
    for pattern in patterns:
        matches = re.findall(pattern, response)
        file_paths.update(matches)

    return list(file_paths)


def extract_suggested_commands_from_response(response: str) -> list[str]:
    """Extract suggested commands from a response."""
    # Look for command suggestions
    patterns = [
        r'`([^`]+)`',  # Commands in backticks
        r'(?:run|execute|try):\s*([^\n]+)',  # Command suggestions
        r'\$\s*([^\n]+)',  # Shell commands
    ]

    commands = set()
    for pattern in patterns:
        matches = re.findall(pattern, response)
        commands.update(matches)

    # Filter out non-command text
    filtered_commands = []
    for cmd in commands:
        if any(keyword in cmd.lower() for keyword in ['python', 'pip', 'pytest', 'mypy', 'git', 'npm']):
            filtered_commands.append(cmd.strip())

    return filtered_commands
