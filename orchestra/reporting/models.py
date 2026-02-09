"""
Report data models for MCP test runs.

This module defines the data structures for capturing complete
run records including metadata, step results, and timing.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    """Status of an individual step execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    """Overall status of a test run."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class StepRecord:
    """
    Record of a single step execution.
    
    Captures everything about a step: what went in, what came out,
    how long it took, and any errors encountered.
    """
    step_id: str
    step_type: str  # "tool_call" or "assert"
    status: StepStatus = StepStatus.PENDING
    
    # Timing
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: float | None = None
    
    # Input/Output
    input_data: dict[str, Any] | None = None
    output_data: Any = None
    
    # For tool_call steps
    tool_name: str | None = None
    
    # For assert steps
    assertion_type: str | None = None  # e.g., "jsonpath_exists"
    assertion_path: str | None = None
    expected_value: Any = None
    actual_value: Any = None
    
    # Errors and messages
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
    failure_message: str | None = None

    def start(self) -> None:
        """Mark the step as started."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, status: StepStatus) -> None:
        """Mark the step as completed with given status."""
        self.status = status
        self.ended_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.ended_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "input_data": self.input_data,
            "output_data": _safe_serialize(self.output_data),
            "tool_name": self.tool_name,
            "assertion_type": self.assertion_type,
            "assertion_path": self.assertion_path,
            "expected_value": _safe_serialize(self.expected_value),
            "actual_value": _safe_serialize(self.actual_value),
            "error_message": self.error_message,
            "error_details": self.error_details,
            "failure_message": self.failure_message,
        }


@dataclass
class RunReport:
    """
    Complete record of a test collection run.
    
    Contains metadata about the run, the collection being tested,
    and detailed records for each step.
    """
    # Run identification
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    duration_ms: float | None = None
    
    # Collection info
    collection_name: str = ""
    collection_version: int = 1
    collection_hash: str = ""
    
    # Server info
    server_transport: str = ""
    server_url: str | None = None
    
    # Overall status
    status: RunStatus = RunStatus.PENDING
    
    # Step records
    steps: list[StepRecord] = field(default_factory=list)
    
    # Summary stats
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    error_steps: int = 0
    skipped_steps: int = 0

    def start(self) -> None:
        """Mark the run as started."""
        self.status = RunStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """Mark the run as completed and calculate final status."""
        self.ended_at = datetime.now(timezone.utc)
        delta = self.ended_at - self.started_at
        self.duration_ms = delta.total_seconds() * 1000
        
        # Calculate summary stats
        self.total_steps = len(self.steps)
        self.passed_steps = sum(1 for s in self.steps if s.status == StepStatus.PASSED)
        self.failed_steps = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        self.error_steps = sum(1 for s in self.steps if s.status == StepStatus.ERROR)
        self.skipped_steps = sum(1 for s in self.steps if s.status == StepStatus.SKIPPED)
        
        # Determine overall status
        if self.error_steps > 0:
            self.status = RunStatus.ERROR
        elif self.failed_steps > 0:
            self.status = RunStatus.FAILED
        else:
            self.status = RunStatus.PASSED

    def add_step(self, step: StepRecord) -> None:
        """Add a step record to the run."""
        self.steps.append(step)

    def get_step(self, step_id: str) -> StepRecord | None:
        """Get a step record by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "collection_name": self.collection_name,
            "collection_version": self.collection_version,
            "collection_hash": self.collection_hash,
            "server_transport": self.server_transport,
            "server_url": self.server_url,
            "status": self.status.value,
            "summary": {
                "total": self.total_steps,
                "passed": self.passed_steps,
                "failed": self.failed_steps,
                "errors": self.error_steps,
                "skipped": self.skipped_steps,
            },
            "steps": [step.to_dict() for step in self.steps],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"═══════════════════════════════════════════════════════════",
            f"  Run Report: {self.collection_name}",
            f"═══════════════════════════════════════════════════════════",
            f"  Run ID:     {self.run_id}",
            f"  Status:     {_status_icon(self.status)} {self.status.value.upper()}",
            f"  Duration:   {self.duration_ms:.0f}ms" if self.duration_ms else "  Duration:   N/A",
            f"  Started:    {self.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.started_at else 'N/A'}",
            f"───────────────────────────────────────────────────────────",
            f"  Steps: {self.passed_steps} passed, {self.failed_steps} failed, {self.error_steps} errors, {self.skipped_steps} skipped",
            f"───────────────────────────────────────────────────────────",
        ]
        
        # Add step details
        for step in self.steps:
            icon = _status_icon_step(step.status)
            duration = f"{step.duration_ms:.0f}ms" if step.duration_ms else "N/A"
            lines.append(f"  {icon} [{step.step_id}] {step.step_type} - {duration}")
            
            if step.failure_message:
                lines.append(f"      └─ {step.failure_message}")
            elif step.error_message:
                lines.append(f"      └─ Error: {step.error_message}")
        
        lines.append(f"═══════════════════════════════════════════════════════════")
        return "\n".join(lines)


def compute_collection_hash(collection_dict: dict[str, Any]) -> str:
    """
    Compute a hash of the collection for tracking/versioning.
    
    Args:
        collection_dict: The collection data as a dict
        
    Returns:
        SHA-256 hash (first 12 chars)
    """
    # Normalize and serialize
    serialized = json.dumps(collection_dict, sort_keys=True, default=str)
    hash_bytes = hashlib.sha256(serialized.encode()).hexdigest()
    return hash_bytes[:12]


def _safe_serialize(value: Any) -> Any:
    """Safely serialize a value, handling non-JSON types."""
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _status_icon(status: RunStatus) -> str:
    """Get icon for run status."""
    return {
        RunStatus.PENDING: "⏳",
        RunStatus.RUNNING: "🔄",
        RunStatus.PASSED: "✅",
        RunStatus.FAILED: "❌",
        RunStatus.ERROR: "⚠️",
    }.get(status, "❓")


def _status_icon_step(status: StepStatus) -> str:
    """Get icon for step status."""
    return {
        StepStatus.PENDING: "⏳",
        StepStatus.RUNNING: "🔄",
        StepStatus.PASSED: "✅",
        StepStatus.FAILED: "❌",
        StepStatus.ERROR: "⚠️",
        StepStatus.SKIPPED: "⏭️",
    }.get(status, "❓")

