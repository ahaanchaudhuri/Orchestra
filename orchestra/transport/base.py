"""
Base transport interface for MCP communication.

This module defines the abstract base class that all transport
implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import MCPRequest, MCPResponse, ToolCallRequest


class BaseTransport(ABC):
    """
    Abstract base class for MCP transports.
    
    Transports handle the low-level communication with MCP servers,
    whether over HTTP, STDIO, or other protocols.
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the MCP server.
        
        For HTTP, this might verify the endpoint is reachable.
        For STDIO, this spawns the subprocess.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close the connection to the MCP server.
        
        For STDIO, this terminates the subprocess.
        """
        pass

    @abstractmethod
    async def send(self, request: MCPRequest, timeout_ms: int = 30000) -> MCPResponse:
        """
        Send a raw MCP JSON-RPC request and get the response.
        
        Args:
            request: The MCP request to send
            timeout_ms: Timeout in milliseconds
            
        Returns:
            MCPResponse with either result or error
        """
        pass

    async def call_tool(self, request: ToolCallRequest) -> MCPResponse:
        """
        High-level method to call an MCP tool.
        
        Args:
            request: The tool call request
            
        Returns:
            MCPResponse with the tool's result or error
        """
        mcp_request = request.to_mcp_request()
        return await self.send(mcp_request, timeout_ms=request.timeout_ms)

    async def initialize(self) -> MCPResponse:
        """
        Send the MCP initialize request.
        
        This should be called after connect() to complete the handshake.
        """
        from .models import MCPRequest
        
        request = MCPRequest(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-test-runner",
                    "version": "0.1.0",
                },
            },
        )
        return await self.send(request)

    async def list_tools(self) -> MCPResponse:
        """
        Request the list of available tools from the server.
        """
        from .models import MCPRequest
        
        request = MCPRequest(method="tools/list", params={})
        return await self.send(request)

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the transport is currently connected."""
        pass

    async def __aenter__(self) -> BaseTransport:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

