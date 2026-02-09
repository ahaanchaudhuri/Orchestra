"""
Reporting for MCP Test Runs

This package provides reporting capabilities for capturing complete
records of test collection runs.

Features:
    - Run metadata (ID, timestamp, collection info)
    - Step-by-step records with timing
    - Input/output capture
    - Error and failure messages
    - JSON serialization
    - Human-readable summaries

Usage:
    from components.schema_parsing import load_collection
    from components.reporting import Reporter
    
    collection, _ = load_collection("collection.yaml")
    reporter = Reporter.from_collection(collection)
    
    # Run execution
    reporter.start_run()
    
    reporter.start_step("search")
    reporter.complete_step_success("search", output={"results": [...]})
    
    reporter.start_step("assert_count")
    reporter.complete_step_failure(
        "assert_count",
        failure_message="Expected 5 results, got 3",
        expected_value=5,
        actual_value=3,
    )
    
    # Get report
    report = reporter.finish_run()
    print(report.summary())
    
    # Save to file
    reporter.save_json("reports/run-2024-01-15.json")
"""

# Models
from .models import (
    RunReport,
    RunStatus,
    StepRecord,
    StepStatus,
    compute_collection_hash,
)

# Reporter
from .reporter import Reporter

__all__ = [
    # Models
    "RunReport",
    "RunStatus",
    "StepRecord",
    "StepStatus",
    "compute_collection_hash",
    # Reporter
    "Reporter",
]

