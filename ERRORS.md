# Error Handling in Agent-S3

Agent-S3 implements comprehensive error handling with pattern detection, Chain of Thought integration, and specialized recovery strategies.

## Error Types

The system recognizes and provides specialized handling for these error types:

1. **Syntax Errors**
   - Pattern detection for common syntax mistakes
   - Validation of proper code structure
   - Recovery suggestions for parentheses, brackets, quotes, and indentation

2. **Type Errors**
   - Variable type validation
   - Type conversion suggestions
   - Function parameter type checking

3. **Import Errors**
   - Package dependency verification
   - Python path validation
   - Requirements.txt analysis

4. **Attribute Errors**
   - Object initialization verification
   - Attribute name validation
   - Instance method availability checks

5. **Name Errors**
   - Variable scope analysis 
   - Import verification
   - Typo detection

6. **Index Errors**
   - Array bounds checking
   - Dictionary key validation
   - Collection size verification

7. **Value Errors**
   - Input validation
   - Data range checking
   - Format verification

8. **Runtime Errors**
   - General execution error handling
   - State validation
   - Resource availability checks

9. **Memory Errors**
   - Memory usage monitoring
   - Resource cleanup suggestions
   - Optimization recommendations

10. **Permission Errors**
    - File access validation
    - Directory permissions checking
    - OS-level security verification

11. **Network Errors**
    - Connectivity checks
    - Endpoint validation
    - Retry strategy suggestions

12. **Database Errors**
    - Connection validation
    - Query syntax checking
    - Database state verification

## Comprehensive Debugging System

The debugging system employs a three-tier approach with Chain of Thought integration:

### Tier 1: Generator Quick Fix
- Fast, targeted fixes for simple issues
- Minimal context requirements
- Pattern-based resolution

### Tier 2: Full Debugging
- Comprehensive analysis with Chain of Thought context
- Multi-file fixes and dependency resolution
- Historical reasoning integration

### Tier 3: Strategic Restart
- Code regeneration: New implementation with same plan
- Plan redesign: Alternative approach to the same goal
- Request modification: Changes to requirements when necessary

See [DEBUGGING.md](DEBUGGING.md) for a detailed breakdown of the debugging system.

## Chain of Thought Integration

The debugging system incorporates Chain of Thought (CoT) logging to improve error resolution:

- **Structured Reasoning**: All reasoning steps are captured in dedicated sections
- **Error-Relevant CoT**: Past reasoning context is matched with current errors
- **Relevance Scoring**: CoT entries are scored based on relevance to errors
- **Contextual Debugging**: Historical context is incorporated into debugging strategies
- **Enhanced Scratchpad Manager**: Dedicated component for managing CoT logging and extraction
- **Section-Based Organization**: Categorizes logging into PLANNING, DEBUGGING, REASONING sections
- **Session Management**: Preserves context across debugging sessions
- **Metadata Tracking**: Includes detailed metadata with each log entry

## Error Pattern Learning

The system maintains a cache of error patterns with:
- Error type classification
- Message pattern matching
- Frequency tracking
- Success rate of recovery strategies
- Timestamp-based pattern pruning

Error patterns older than 7 days or with less than 5 occurrences are automatically pruned to maintain cache efficiency.

## Recovery Strategy Selection

For each error, the system:
1. Matches against known patterns
2. Gathers specialized context based on error type
3. Extracts relevant Chain of Thought from previous reasoning
4. Generates targeted recovery suggestions with increasing sophistication
5. Applies role-specific context allocation
6. Tracks success rates of recovery strategies

## Context Management

When handling errors, the system uses smart token allocation:
- Primary error location gets 30% of context budget
- Related files share 50% of context budget
- Error pattern matching uses 10% of budget
- Chain of Thought context gets 10% of budget

Files are selected based on:
1. Primary error location
2. Stack trace references
3. Semantic search results
4. Recently debugged files

## Specialized Context Gathering

Different error types trigger specific context gathering:

### Import Errors
- Python path validation
- Requirements.txt scanning
- Site-packages location check
- Package metadata retrieval

### Permission Errors
- File permission details
- Owner/group information
- Access flag validation
- Directory structure analysis

### Network Errors
- DNS resolution checks
- HTTP/HTTPS connectivity
- Connection timeout detection
- Endpoint availability validation

### Database Errors
- Connection string validation
- Authentication verification
- Database state checking
- Query context analysis

## Integration with Other Components

The error handling system integrates with:
- Enhanced Scratchpad Manager for CoT logging
- Router Agent for LLM selection
- Code Generator for fix attempts
- Memory Manager for context
- Code Analysis Tool for semantic search
- Progress Tracker for status updates

## Usage in Development

When developing with Agent-S3:
1. Errors are automatically detected and classified
2. The system gathers relevant context and Chain of Thought
3. Recovery suggestions escalate through the three tiers
4. Pattern matching helps identify known solutions
5. Success/failure is tracked for future optimization

## Recovery Example

For a typical error:
```python
ImportError: No module named 'requests'
```

The system will:
1. Classify as Import Error
2. Check requirements.txt and virtual environment
3. Validate Python path
4. Look for similar past errors
5. Extract relevant Chain of Thought context
6. Suggest: "Install requests package" with exact command
7. Track if the suggestion resolves the error

## Configuration

Error handling can be configured via:
- Token budget allocation in router_agent.py
- Pattern retention period in error_context_manager.py
- Similarity threshold for pattern matching
- Context gathering depth per error type
- CoT extraction settings in enhanced_scratchpad_manager.py