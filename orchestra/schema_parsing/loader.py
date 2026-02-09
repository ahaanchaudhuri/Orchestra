"""
Collection loader for MCP test collections.

This module provides the public API for loading and validating
collection files from disk or YAML strings.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Collection
from .parser import SchemaParser
from .validation import SchemaValidator, ValidationResult


def load_collection(path: str | Path) -> tuple[Collection | None, ValidationResult]:
    """
    Load and validate a collection from a YAML file.

    Args:
        path: Path to the YAML collection file

    Returns:
        Tuple of (Collection or None, ValidationResult)
        If validation fails, Collection will be None.

    Example:
        collection, result = load_collection("schemas/collection.yaml")
        if not result.is_valid:
            print(result)
            sys.exit(1)
        # Use collection...
    """
    path = Path(path)

    # Check file exists
    if not path.exists():
        result = ValidationResult()
        result.add_error(
            str(path),
            "File not found",
            suggestion="Check the file path is correct"
        )
        return None, result

    # Parse YAML
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result = ValidationResult()
        result.add_error(
            str(path),
            f"Invalid YAML syntax: {e}",
            suggestion="Check YAML formatting (indentation, colons, etc.)"
        )
        return None, result

    if not isinstance(data, dict):
        result = ValidationResult()
        result.add_error(
            str(path),
            "File must contain a YAML object (not a list or scalar)",
            value=type(data).__name__
        )
        return None, result

    # Validate schema
    validator = SchemaValidator(data)
    result = validator.validate()

    if not result.is_valid:
        return None, result

    # Parse to typed structure
    parser = SchemaParser(data)
    collection = parser.parse()

    return collection, result


def validate_collection_yaml(yaml_string: str) -> tuple[Collection | None, ValidationResult]:
    """
    Validate a collection from a YAML string (useful for testing).

    Args:
        yaml_string: YAML content as a string

    Returns:
        Tuple of (Collection or None, ValidationResult)
    """
    try:
        data = yaml.safe_load(yaml_string)
    except yaml.YAMLError as e:
        result = ValidationResult()
        result.add_error("yaml", f"Invalid YAML syntax: {e}")
        return None, result

    if not isinstance(data, dict):
        result = ValidationResult()
        result.add_error(
            "yaml",
            "Content must be a YAML object",
            value=type(data).__name__
        )
        return None, result

    validator = SchemaValidator(data)
    result = validator.validate()

    if not result.is_valid:
        return None, result

    parser = SchemaParser(data)
    return parser.parse(), result

