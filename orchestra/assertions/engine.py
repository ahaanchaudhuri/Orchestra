"""
Assertion engine for evaluating checks on JSON data.

This module provides the core assertion logic for verifying
MCP response data against expected conditions.
"""

from __future__ import annotations

from typing import Any

from jsonpath_ng import parse as parse_jsonpath
from jsonpath_ng.exceptions import JsonPathParserError

from .models import AssertionResult


class AssertionEngine:
    """
    Engine for running assertions on JSON data.
    
    Supports various assertion types:
    - exists: Check if a path exists in the data
    - equals: Check if a value equals an expected value
    - contains: Check if a string/array contains a value
    - length_gte: Check if an array has at least N items
    - length_lte: Check if an array has at most N items
    - length_eq: Check if an array has exactly N items
    
    Example:
        engine = AssertionEngine()
        data = {"results": [{"id": 1}, {"id": 2}]}
        
        result = engine.exists(data, "$.results[0]")
        result = engine.length_gte(data, "$.results", 1)
        result = engine.equals(data, "$.results[0].id", 1)
    """

    def exists(self, data: Any, path: str) -> AssertionResult:
        """
        Assert that a path exists in the data.
        
        Args:
            data: The JSON data to search
            path: JSONPath expression
            
        Returns:
            AssertionResult indicating pass/fail
        """
        matches, error = self._evaluate_path(data, path)
        if error:
            return error

        if matches:
            return AssertionResult.passed_result(
                message=f"Path exists",
                path=path,
                actual=self._summarize_matches(matches),
            )
        else:
            return AssertionResult.failed_result(
                message=f"Path does not exist",
                path=path,
                expected="path to exist",
                actual="no matches found",
            )

    def equals(self, data: Any, path: str, expected: Any) -> AssertionResult:
        """
        Assert that the value at a path equals an expected value.
        
        Args:
            data: The JSON data to search
            path: JSONPath expression
            expected: The expected value
            
        Returns:
            AssertionResult indicating pass/fail
        """
        matches, error = self._evaluate_path(data, path)
        if error:
            return error

        if not matches:
            return AssertionResult.failed_result(
                message=f"Path does not exist",
                path=path,
                expected=expected,
                actual="<path not found>",
            )

        # Get the first match value
        actual = matches[0].value

        if actual == expected:
            return AssertionResult.passed_result(
                message=f"Value matches expected",
                path=path,
                actual=actual,
            )
        else:
            return AssertionResult.failed_result(
                message=f"Value does not match",
                path=path,
                expected=expected,
                actual=actual,
                details=self._type_mismatch_hint(expected, actual),
            )

    def contains(self, data: Any, path: str, expected: Any) -> AssertionResult:
        """
        Assert that the value at a path contains an expected value.
        
        Works with:
        - Strings: checks if expected is a substring
        - Arrays: checks if expected is an element
        - Dicts: checks if expected is a key
        
        Args:
            data: The JSON data to search
            path: JSONPath expression  
            expected: The value to look for
            
        Returns:
            AssertionResult indicating pass/fail
        """
        matches, error = self._evaluate_path(data, path)
        if error:
            return error

        if not matches:
            return AssertionResult.failed_result(
                message=f"Path does not exist",
                path=path,
                expected=f"container with {expected!r}",
                actual="<path not found>",
            )

        actual = matches[0].value

        # Check containment based on type
        if isinstance(actual, str):
            if not isinstance(expected, str):
                return AssertionResult.failed_result(
                    message=f"Cannot check if string contains non-string",
                    path=path,
                    expected=expected,
                    actual=actual,
                    details={"hint": "Expected value should be a string for substring check"},
                )
            if expected in actual:
                return AssertionResult.passed_result(
                    message=f"String contains expected substring",
                    path=path,
                    actual=actual,
                )
            else:
                return AssertionResult.failed_result(
                    message=f"String does not contain expected substring",
                    path=path,
                    expected=f"string containing {expected!r}",
                    actual=actual,
                )

        elif isinstance(actual, list):
            if expected in actual:
                return AssertionResult.passed_result(
                    message=f"Array contains expected value",
                    path=path,
                    actual=actual,
                )
            else:
                return AssertionResult.failed_result(
                    message=f"Array does not contain expected value",
                    path=path,
                    expected=f"array containing {expected!r}",
                    actual=actual,
                    details={"array_length": len(actual)},
                )

        elif isinstance(actual, dict):
            if expected in actual:
                return AssertionResult.passed_result(
                    message=f"Object contains expected key",
                    path=path,
                    actual=list(actual.keys()),
                )
            else:
                return AssertionResult.failed_result(
                    message=f"Object does not contain expected key",
                    path=path,
                    expected=f"object with key {expected!r}",
                    actual=list(actual.keys()),
                )

        else:
            return AssertionResult.error_result(
                message=f"Cannot check containment on {type(actual).__name__}",
                path=path,
                details={"type": type(actual).__name__, "value": actual},
            )

    def length_gte(self, data: Any, path: str, min_length: int) -> AssertionResult:
        """
        Assert that an array at the path has at least N items.
        
        Args:
            data: The JSON data to search
            path: JSONPath expression
            min_length: Minimum required length
            
        Returns:
            AssertionResult indicating pass/fail
        """
        return self._check_length(data, path, min_length, "gte")

    def length_lte(self, data: Any, path: str, max_length: int) -> AssertionResult:
        """
        Assert that an array at the path has at most N items.
        
        Args:
            data: The JSON data to search
            path: JSONPath expression
            max_length: Maximum allowed length
            
        Returns:
            AssertionResult indicating pass/fail
        """
        return self._check_length(data, path, max_length, "lte")

    def length_eq(self, data: Any, path: str, exact_length: int) -> AssertionResult:
        """
        Assert that an array at the path has exactly N items.
        
        Args:
            data: The JSON data to search
            path: JSONPath expression
            exact_length: Required exact length
            
        Returns:
            AssertionResult indicating pass/fail
        """
        return self._check_length(data, path, exact_length, "eq")

    def is_error(self, data: Any) -> AssertionResult:
        """
        Assert that an MCP response has isError=true.
        
        Args:
            data: The JSON data from an MCP tool call response
            
        Returns:
            AssertionResult indicating pass/fail
        """
        is_error = data.get("isError", False) if isinstance(data, dict) else False
        
        if is_error:
            error_text = ""
            if isinstance(data, dict) and "content" in data:
                content = data["content"]
                if isinstance(content, list) and len(content) > 0:
                    error_text = content[0].get("text", "")
            
            return AssertionResult.passed_result(
                message="Response has isError=true as expected",
                actual=f"Error: {error_text}" if error_text else "isError=true",
            )
        else:
            return AssertionResult.failed_result(
                message="Response does not have isError=true",
                expected="isError=true",
                actual="isError=false or missing",
            )

    def no_error(self, data: Any) -> AssertionResult:
        """
        Assert that an MCP response does NOT have isError=true.
        
        Args:
            data: The JSON data from an MCP tool call response
            
        Returns:
            AssertionResult indicating pass/fail
        """
        is_error = data.get("isError", False) if isinstance(data, dict) else False
        
        if not is_error:
            return AssertionResult.passed_result(
                message="Response has no error flag",
                actual="isError=false or missing",
            )
        else:
            error_text = ""
            if isinstance(data, dict) and "content" in data:
                content = data["content"]
                if isinstance(content, list) and len(content) > 0:
                    error_text = content[0].get("text", "")
            
            return AssertionResult.failed_result(
                message="Response has isError=true",
                expected="no error",
                actual=f"Error: {error_text}" if error_text else "isError=true",
            )

    def _check_length(
        self, data: Any, path: str, expected_length: int, op: str
    ) -> AssertionResult:
        """Internal helper for length checks."""
        matches, error = self._evaluate_path(data, path)
        if error:
            return error

        if not matches:
            return AssertionResult.failed_result(
                message=f"Path does not exist",
                path=path,
                expected=f"array with length check",
                actual="<path not found>",
            )

        actual = matches[0].value

        if not isinstance(actual, (list, str)):
            return AssertionResult.error_result(
                message=f"Cannot check length of {type(actual).__name__}",
                path=path,
                details={"type": type(actual).__name__},
            )

        actual_length = len(actual)
        type_name = "array" if isinstance(actual, list) else "string"

        if op == "gte":
            if actual_length >= expected_length:
                return AssertionResult.passed_result(
                    message=f"{type_name.capitalize()} has at least {expected_length} items",
                    path=path,
                    actual=f"length {actual_length}",
                )
            else:
                return AssertionResult.failed_result(
                    message=f"{type_name.capitalize()} is too short",
                    path=path,
                    expected=f"length >= {expected_length}",
                    actual=f"length {actual_length}",
                    details={"difference": expected_length - actual_length},
                )

        elif op == "lte":
            if actual_length <= expected_length:
                return AssertionResult.passed_result(
                    message=f"{type_name.capitalize()} has at most {expected_length} items",
                    path=path,
                    actual=f"length {actual_length}",
                )
            else:
                return AssertionResult.failed_result(
                    message=f"{type_name.capitalize()} is too long",
                    path=path,
                    expected=f"length <= {expected_length}",
                    actual=f"length {actual_length}",
                    details={"excess": actual_length - expected_length},
                )

        else:  # eq
            if actual_length == expected_length:
                return AssertionResult.passed_result(
                    message=f"{type_name.capitalize()} has exactly {expected_length} items",
                    path=path,
                    actual=f"length {actual_length}",
                )
            else:
                return AssertionResult.failed_result(
                    message=f"{type_name.capitalize()} length mismatch",
                    path=path,
                    expected=f"length == {expected_length}",
                    actual=f"length {actual_length}",
                    details={"difference": abs(actual_length - expected_length)},
                )

    def _evaluate_path(self, data: Any, path: str) -> tuple[list, AssertionResult | None]:
        """
        Evaluate a JSONPath expression on data.
        
        Returns:
            Tuple of (matches, error). If error is not None, matches is empty.
        """
        try:
            jsonpath_expr = parse_jsonpath(path)
        except JsonPathParserError as e:
            return [], AssertionResult.error_result(
                message=f"Invalid JSONPath expression",
                path=path,
                details={"error": str(e)},
            )
        except Exception as e:
            return [], AssertionResult.error_result(
                message=f"Failed to parse JSONPath",
                path=path,
                details={"error": f"{type(e).__name__}: {e}"},
            )

        try:
            matches = jsonpath_expr.find(data)
            return matches, None
        except Exception as e:
            return [], AssertionResult.error_result(
                message=f"Failed to evaluate JSONPath",
                path=path,
                details={"error": f"{type(e).__name__}: {e}"},
            )

    def _summarize_matches(self, matches: list) -> Any:
        """Summarize matches for display."""
        if len(matches) == 1:
            return matches[0].value
        return [m.value for m in matches]

    def _type_mismatch_hint(self, expected: Any, actual: Any) -> dict[str, Any]:
        """Generate a hint if types don't match."""
        if type(expected) != type(actual):
            return {
                "hint": f"Type mismatch: expected {type(expected).__name__}, got {type(actual).__name__}"
            }
        return {}


# Convenience function for quick assertions
def assert_path_exists(data: Any, path: str) -> AssertionResult:
    """Check if a JSONPath exists in the data."""
    return AssertionEngine().exists(data, path)


def assert_equals(data: Any, path: str, expected: Any) -> AssertionResult:
    """Check if the value at a JSONPath equals expected."""
    return AssertionEngine().equals(data, path, expected)


def assert_contains(data: Any, path: str, expected: Any) -> AssertionResult:
    """Check if the value at a JSONPath contains expected."""
    return AssertionEngine().contains(data, path, expected)


def assert_length_gte(data: Any, path: str, min_length: int) -> AssertionResult:
    """Check if the array at a JSONPath has at least N items."""
    return AssertionEngine().length_gte(data, path, min_length)

