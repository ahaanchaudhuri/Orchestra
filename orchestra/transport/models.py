"""
Transport layer models for MCP communication.

This module defines the data structures for MCP JSON-RPC requests,
responses, and error handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class MCPErrorCode(IntEnum):
    """Standard JSON-RPC 2.0 and MCP error codes."""
    # JSON-RPC 2.0 standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Transport-level errors (custom)
    CONNECTION_ERROR = -32000
    TIMEOUT_ERROR = -32001
    PROCESS_ERROR = -32002


@dataclass
class MCPError:
    """Represents an MCP/JSON-RPC error."""
    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPError:
        return cls(
            code=data.get("code", MCPErrorCode.INTERNAL_ERROR),
            message=data.get("message", "Unknown error"),
            data=data.get("data"),
        )

    @classmethod
    def connection_error(cls, message: str, data: Any = None) -> MCPError:
        return cls(MCPErrorCode.CONNECTION_ERROR, message, data)

    @classmethod
    def timeout_error(cls, message: str, data: Any = None) -> MCPError:
        return cls(MCPErrorCode.TIMEOUT_ERROR, message, data)

    @classmethod
    def process_error(cls, message: str, data: Any = None) -> MCPError:
        return cls(MCPErrorCode.PROCESS_ERROR, message, data)


@dataclass
class MCPRequest:
    """Represents an MCP JSON-RPC request."""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: int | str = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id,
        }


@dataclass
class MCPResponse:
    """Represents the result of an MCP call."""
    success: bool
    result: Any = None
    error: MCPError | None = None
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        if self.success:
            return {
                "success": True,
                "result": self.result,
            }
        else:
            return {
                "success": False,
                "error": self.error.to_dict() if self.error else None,
            }

    @classmethod
    def from_jsonrpc(cls, data: dict[str, Any]) -> MCPResponse:
        """Parse a JSON-RPC 2.0 response."""
        if "error" in data:
            return cls(
                success=False,
                error=MCPError.from_dict(data["error"]),
                raw_response=data,
            )
        return cls(
            success=True,
            result=data.get("result"),
            raw_response=data,
        )

    @classmethod
    def from_error(cls, error: MCPError) -> MCPResponse:
        """Create a response from a transport-level error."""
        return cls(success=False, error=error)


@dataclass
class ToolCallRequest:
    """High-level request to call an MCP tool."""
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000

    def to_mcp_request(self, request_id: int = 1) -> MCPRequest:
        """Convert to MCP JSON-RPC request format."""
        return MCPRequest(
            method="tools/call",
            params={
                "name": self.tool_name,
                "arguments": self.arguments,
            },
            id=request_id,
        )

