"""
Schema Parsing for MCP Test Collections

This package provides tools for parsing, validating, and working with
MCP test collection schemas.

Usage:
    from components.schema_parsing import load_collection, validate_collection_yaml

    # Load from file
    collection, result = load_collection("schemas/collection.yaml")
    if not result.is_valid:
        print(result)
    
    # Or validate from string
    collection, result = validate_collection_yaml(yaml_string)
"""

# Public API
from .loader import load_collection, load_server_config, validate_collection_yaml

# Models (for type hints and isinstance checks)
from .models import (
    AssertCheck,
    AssertOp,
    AssertStep,
    AuthConfig,
    AuthType,
    Collection,
    Defaults,
    ServerConfig,
    Step,
    StepType,
    ToolCallStep,
    TransportType,
)

# Validation (for custom validation if needed)
from .validation import SchemaValidator, ValidationError, ValidationResult

__all__ = [
    # Loader functions
    "load_collection",
    "load_server_config",
    "validate_collection_yaml",
    # Models
    "Collection",
    "ServerConfig",
    "Defaults",
    "Step",
    "ToolCallStep",
    "AssertStep",
    "AssertCheck",
    "StepType",
    "AssertOp",
    "TransportType",
    "AuthConfig",
    "AuthType",
    # Validation
    "ValidationResult",
    "ValidationError",
    "SchemaValidator",
]

