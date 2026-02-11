"""
Typed data structures for MCP test collections.

This module contains all enums and dataclasses that represent
the internal typed structure of a parsed collection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Union


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class StepType(str, Enum):
    """Type of step in a collection."""
    TOOL_CALL = "tool_call"
    ASSERT = "assert"


class AssertOp(str, Enum):
    """Supported assertion operators."""
    JSONPATH_EXISTS = "jsonpath_exists"
    JSONPATH_LEN_GTE = "jsonpath_len_gte"
    JSONPATH_LEN_LTE = "jsonpath_len_lte"
    JSONPATH_LEN_EQ = "jsonpath_len_eq"
    JSONPATH_EQ = "jsonpath_eq"
    JSONPATH_CONTAINS = "jsonpath_contains"
    IS_ERROR = "is_error"  # Check if MCP response has isError=true
    NO_ERROR = "no_error"  # Check if MCP response has isError=false or missing


class TransportType(str, Enum):
    """MCP server transport types."""
    HTTP = "http"
    STDIO = "stdio"
    SSE = "sse"  # SSE-based transport (older MCP pattern)


class AuthType(str, Enum):
    """Supported authentication types for HTTP transport."""
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"


# ─────────────────────────────────────────────────────────────────────────────
# Auth Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthConfig:
    """
    Authentication configuration for HTTP transport.
    
    Supports three auth types:
    - bearer: Uses Authorization: Bearer <token> header
    - api_key: Uses a custom header with the API key
    - basic: Uses Authorization: Basic <base64(user:pass)> header
    """
    type: AuthType
    # For bearer auth
    token: str | None = None
    # For api_key auth
    header: str = "X-API-Key"
    key: str | None = None
    # For basic auth
    username: str | None = None
    password: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Server & Defaults
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ServerConfig:
    """Configuration for connecting to an MCP server."""
    transport: TransportType
    url: str | None = None  # Required for HTTP/SSE
    command: str | None = None  # Required for STDIO
    args: list[str] = field(default_factory=list)
    auth: AuthConfig | None = None  # Optional auth for HTTP/SSE
    env: dict[str, str] = field(default_factory=dict)  # Environment variables for STDIO


@dataclass
class Defaults:
    """Default settings for step execution."""
    timeout_ms: int = 30000
    retries: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Steps
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AssertCheck:
    """Assertion check configuration."""
    op: AssertOp
    path: str
    value: Any = None  # Optional, depends on op


@dataclass
class ToolCallStep:
    """A step that calls an MCP tool."""
    id: str
    type: Literal[StepType.TOOL_CALL] = StepType.TOOL_CALL
    tool: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    save: str | None = None  # JSONPath expression for what to save
    delay_ms: int | None = None  # Optional delay after step execution


@dataclass
class AssertStep:
    """A step that asserts on a previous step's output."""
    id: str
    type: Literal[StepType.ASSERT] = StepType.ASSERT
    from_step: str = ""  # 'from' in YAML, renamed to avoid keyword
    check: AssertCheck | None = None
    delay_ms: int | None = None  # Optional delay after step execution


# Union type for all step variants
Step = Union[ToolCallStep, AssertStep]


# ─────────────────────────────────────────────────────────────────────────────
# Collection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Collection:
    """Fully parsed and validated collection."""
    version: int
    name: str
    server: ServerConfig
    env: dict[str, Any] = field(default_factory=dict)
    defaults: Defaults = field(default_factory=Defaults)
    steps: list[Step] = field(default_factory=list)

