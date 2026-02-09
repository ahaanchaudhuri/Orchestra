"""
MCP Transport Layer

This package provides transport implementations for communicating with
MCP servers over different protocols (HTTP, STDIO).

Usage:
    from components.transport import create_transport, HTTPTransport, STDIOTransport
    from components.schema_parsing import load_collection
    
    # Create from config
    collection, _ = load_collection("collection.yaml")
    transport = create_transport(collection.server)
    
    # Or create directly
    transport = HTTPTransport("http://localhost:8000")
    
    # Use as async context manager
    async with transport:
        response = await transport.call_tool(ToolCallRequest(
            tool_name="search",
            arguments={"query": "hello"}
        ))
        
        if response.success:
            print(response.result)
        else:
            print(response.error)
"""

# Factory
from .factory import create_transport

# Transport implementations
from .base import BaseTransport
from .http import HTTPTransport, StreamableHTTPTransport
from .stdio import STDIOTransport

# Models
from .models import (
    MCPError,
    MCPErrorCode,
    MCPRequest,
    MCPResponse,
    ToolCallRequest,
)

__all__ = [
    # Factory
    "create_transport",
    # Base
    "BaseTransport",
    # Implementations
    "HTTPTransport",
    "StreamableHTTPTransport",
    "STDIOTransport",
    # Models
    "MCPError",
    "MCPErrorCode",
    "MCPRequest",
    "MCPResponse",
    "ToolCallRequest",
]

