"""
Assertion Engine for MCP Response Validation

This package provides assertion capabilities for validating
MCP response data against expected conditions.

Supported assertions:
    - exists: Check if a JSONPath exists in data
    - equals: Check if a value at a path equals expected
    - contains: Check if a string/array/object contains a value
    - length_gte: Check if array has at least N items
    - length_lte: Check if array has at most N items
    - length_eq: Check if array has exactly N items

Usage:
    from components.assertions import AssertionEngine, assert_path_exists
    
    data = {"results": [{"id": 1}, {"id": 2}]}
    
    # Using the engine
    engine = AssertionEngine()
    result = engine.exists(data, "$.results[0]")
    result = engine.length_gte(data, "$.results", 1)
    result = engine.equals(data, "$.results[0].id", 1)
    
    # Using convenience functions
    result = assert_path_exists(data, "$.results[0]")
    
    # Check result
    if result.passed:
        print("✅ Assertion passed")
    else:
        print(result)  # Detailed failure message
"""

# Models
from .models import AssertionResult, AssertionStatus

# Engine
from .engine import (
    AssertionEngine,
    # Convenience functions
    assert_path_exists,
    assert_equals,
    assert_contains,
    assert_length_gte,
)

__all__ = [
    # Models
    "AssertionResult",
    "AssertionStatus",
    # Engine
    "AssertionEngine",
    # Convenience functions
    "assert_path_exists",
    "assert_equals",
    "assert_contains",
    "assert_length_gte",
]

