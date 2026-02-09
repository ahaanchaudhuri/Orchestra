"""
Reporter for building and managing run reports.

This module provides the Reporter class which helps construct
run reports from collection executions.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import (
    RunReport,
    RunStatus,
    StepRecord,
    StepStatus,
    compute_collection_hash,
)

if TYPE_CHECKING:
    from ..schema_parsing import Collection


class Reporter:
    """
    Builds and manages run reports.
    
    The Reporter provides a convenient interface for creating reports
    from Collection objects and recording step results.
    
    Example:
        from components.schema_parsing import load_collection
        from components.reporting import Reporter
        
        collection, _ = load_collection("collection.yaml")
        reporter = Reporter.from_collection(collection)
        
        # Start the run
        reporter.start_run()
        
        # Record steps
        reporter.start_step("search")
        reporter.complete_step_success("search", output={"results": [...]})
        
        reporter.start_step("assert_results")
        reporter.complete_step_failure("assert_results", failure_message="Expected 5 results, got 3")
        
        # Finish and get report
        report = reporter.finish_run()
        print(report.summary())
    """

    def __init__(self, report: RunReport):
        """
        Initialize with a RunReport.
        
        Use Reporter.from_collection() for the typical case.
        """
        self.report = report

    @classmethod
    def from_collection(
        cls,
        collection: Collection,
        run_id: str | None = None,
    ) -> Reporter:
        """
        Create a Reporter from a parsed Collection.
        
        Args:
            collection: The parsed collection to create a report for
            run_id: Optional custom run ID (auto-generated if not provided)
            
        Returns:
            Reporter instance ready to record step results
        """
        # Compute collection hash from its data
        collection_dict = _collection_to_dict(collection)
        collection_hash = compute_collection_hash(collection_dict)

        report = RunReport(
            collection_name=collection.name,
            collection_version=collection.version,
            collection_hash=collection_hash,
            server_transport=collection.server.transport.value,
            server_url=collection.server.url,
        )

        if run_id:
            report.run_id = run_id

        # Pre-populate step records from collection steps
        for step in collection.steps:
            step_record = StepRecord(
                step_id=step.id,
                step_type=step.type.value,
            )

            # Add step-specific info
            if step.type.value == "tool_call":
                step_record.tool_name = step.tool
                step_record.input_data = step.input
            elif step.type.value == "assert":
                if step.check:
                    step_record.assertion_type = step.check.op.value
                    step_record.assertion_path = step.check.path
                    step_record.expected_value = step.check.value

            report.add_step(step_record)

        return cls(report)

    def start_run(self) -> None:
        """Mark the run as started."""
        self.report.start()

    def finish_run(self) -> RunReport:
        """
        Mark the run as completed and return the final report.
        
        Returns:
            The completed RunReport with summary stats
        """
        self.report.complete()
        return self.report

    def start_step(self, step_id: str) -> StepRecord | None:
        """
        Mark a step as started.
        
        Args:
            step_id: The ID of the step to start
            
        Returns:
            The StepRecord, or None if step not found
        """
        step = self.report.get_step(step_id)
        if step:
            step.start()
        return step

    def complete_step_success(
        self,
        step_id: str,
        output: Any = None,
        actual_value: Any = None,
    ) -> StepRecord | None:
        """
        Mark a step as successfully completed.
        
        Args:
            step_id: The ID of the step
            output: The output data from the step
            actual_value: For assertions, the actual value found
            
        Returns:
            The StepRecord, or None if step not found
        """
        step = self.report.get_step(step_id)
        if step:
            step.output_data = output
            step.actual_value = actual_value
            step.complete(StepStatus.PASSED)
        return step

    def complete_step_failure(
        self,
        step_id: str,
        failure_message: str,
        output: Any = None,
        expected_value: Any = None,
        actual_value: Any = None,
    ) -> StepRecord | None:
        """
        Mark a step as failed.
        
        Args:
            step_id: The ID of the step
            failure_message: Human-readable failure description
            output: The output data from the step
            expected_value: What was expected
            actual_value: What was actually found
            
        Returns:
            The StepRecord, or None if step not found
        """
        step = self.report.get_step(step_id)
        if step:
            step.output_data = output
            step.expected_value = expected_value if expected_value is not None else step.expected_value
            step.actual_value = actual_value
            step.failure_message = failure_message
            step.complete(StepStatus.FAILED)
        return step

    def complete_step_error(
        self,
        step_id: str,
        error_message: str,
        error_details: dict[str, Any] | None = None,
    ) -> StepRecord | None:
        """
        Mark a step as errored (not a test failure, but an execution error).
        
        Args:
            step_id: The ID of the step
            error_message: Error description
            error_details: Additional error context
            
        Returns:
            The StepRecord, or None if step not found
        """
        step = self.report.get_step(step_id)
        if step:
            step.error_message = error_message
            step.error_details = error_details
            step.complete(StepStatus.ERROR)
        return step

    def skip_step(self, step_id: str, reason: str | None = None) -> StepRecord | None:
        """
        Mark a step as skipped.
        
        Args:
            step_id: The ID of the step
            reason: Optional reason for skipping
            
        Returns:
            The StepRecord, or None if step not found
        """
        step = self.report.get_step(step_id)
        if step:
            if reason:
                step.failure_message = f"Skipped: {reason}"
            step.complete(StepStatus.SKIPPED)
        return step

    def save_json(self, path: str | Path) -> None:
        """
        Save the report to a JSON file.
        
        Args:
            path: Path to save the JSON file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.report.to_json())

    def get_summary(self) -> str:
        """Get a human-readable summary of the run."""
        return self.report.summary()


def _collection_to_dict(collection: Collection) -> dict[str, Any]:
    """Convert a Collection to a dict for hashing."""
    from ..schema_parsing import ToolCallStep, AssertStep

    steps = []
    for step in collection.steps:
        if isinstance(step, ToolCallStep):
            steps.append({
                "id": step.id,
                "type": step.type.value,
                "tool": step.tool,
                "input": step.input,
                "save": step.save,
            })
        elif isinstance(step, AssertStep):
            steps.append({
                "id": step.id,
                "type": step.type.value,
                "from": step.from_step,
                "check": {
                    "op": step.check.op.value if step.check else None,
                    "path": step.check.path if step.check else None,
                    "value": step.check.value if step.check else None,
                } if step.check else None,
            })

    return {
        "version": collection.version,
        "name": collection.name,
        "server": {
            "transport": collection.server.transport.value,
            "url": collection.server.url,
            "command": collection.server.command,
            "args": collection.server.args,
        },
        "env": collection.env,
        "defaults": {
            "timeout_ms": collection.defaults.timeout_ms,
            "retries": collection.defaults.retries,
        },
        "steps": steps,
    }

