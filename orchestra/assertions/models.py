"""
Assertion result models.

This module defines data structures for assertion outcomes,
including detailed failure information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssertionStatus(str, Enum):
    """Status of an assertion check."""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"  # e.g., invalid path, malformed data


@dataclass
class AssertionResult:
    """
    Result of a single assertion check.
    
    Attributes:
        status: Whether the assertion passed, failed, or errored
        message: Human-readable description of the result
        path: The JSONPath that was evaluated
        expected: What was expected (for comparison assertions)
        actual: What was actually found
        details: Additional context for debugging
    """
    status: AssertionStatus
    message: str
    path: str | None = None
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == AssertionStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status == AssertionStatus.FAILED

    def __str__(self) -> str:
        """Format as a human-readable string."""
        if self.status == AssertionStatus.PASSED:
            return f"✅ PASS: {self.message}"

        icon = "❌" if self.status == AssertionStatus.FAILED else "⚠️"
        lines = [f"{icon} {self.status.value.upper()}: {self.message}"]

        if self.path:
            lines.append(f"   Path: {self.path}")

        if self.expected is not None:
            lines.append(f"   Expected: {_format_value(self.expected)}")

        if self.actual is not None:
            lines.append(f"   Actual:   {_format_value(self.actual)}")

        if self.details:
            for key, value in self.details.items():
                lines.append(f"   {key}: {_format_value(value)}")

        return "\n".join(lines)

    @classmethod
    def passed_result(
        cls,
        message: str,
        path: str | None = None,
        actual: Any = None,
    ) -> AssertionResult:
        """Create a passing result."""
        return cls(
            status=AssertionStatus.PASSED,
            message=message,
            path=path,
            actual=actual,
        )

    @classmethod
    def failed_result(
        cls,
        message: str,
        path: str | None = None,
        expected: Any = None,
        actual: Any = None,
        details: dict[str, Any] | None = None,
    ) -> AssertionResult:
        """Create a failing result."""
        return cls(
            status=AssertionStatus.FAILED,
            message=message,
            path=path,
            expected=expected,
            actual=actual,
            details=details or {},
        )

    @classmethod
    def error_result(
        cls,
        message: str,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AssertionResult:
        """Create an error result (assertion couldn't be evaluated)."""
        return cls(
            status=AssertionStatus.ERROR,
            message=message,
            path=path,
            details=details or {},
        )


def _format_value(value: Any, max_length: int = 100) -> str:
    """Format a value for display, truncating if too long."""
    if value is None:
        return "null"

    if isinstance(value, str):
        formatted = repr(value)
    elif isinstance(value, (list, dict)):
        import json
        try:
            formatted = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            formatted = repr(value)
    else:
        formatted = repr(value)

    if len(formatted) > max_length:
        return formatted[: max_length - 3] + "..."

    return formatted

