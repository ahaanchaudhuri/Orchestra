"""
Streamable HTTP transport for MCP communication.

This module implements the MCP Streamable HTTP transport, which supports:
- JSON-RPC 2.0 over HTTP POST
- Server-Sent Events (SSE) for streaming responses
- Session management via mcp-session-id header
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, TYPE_CHECKING

import aiohttp

from .base import BaseTransport
from .models import MCPError, MCPRequest, MCPResponse

if TYPE_CHECKING:
    from components.schema_parsing.models import AuthConfig

logger = logging.getLogger(__name__)

# MCP Streamable HTTP headers
CONTENT_TYPE = "Content-Type"
ACCEPT = "Accept"
MCP_SESSION_ID = "mcp-session-id"
MCP_PROTOCOL_VERSION = "mcp-protocol-version"

# Content types
JSON_CONTENT_TYPE = "application/json"
SSE_CONTENT_TYPE = "text/event-stream"


class StreamableHTTPTransport(BaseTransport):
    """
    MCP Streamable HTTP transport.
    
    Implements the MCP Streamable HTTP transport protocol which supports:
    - HTTP POST with JSON-RPC 2.0 payloads
    - SSE (Server-Sent Events) for streaming responses
    - Session management via mcp-session-id header
    """

    def __init__(self, url: str, auth_config: "AuthConfig | None" = None):
        """
        Initialize Streamable HTTP transport.
        
        Args:
            url: The MCP server endpoint URL (e.g., "http://localhost:8000/mcp")
            auth_config: Optional authentication configuration
        """
        self.url = url.rstrip("/")
        self._auth_config = auth_config
        self._session: aiohttp.ClientSession | None = None
        self._connected = False
        self._mcp_session_id: str | None = None
        self._protocol_version: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    @property
    def session_id(self) -> str | None:
        """Get the current MCP session ID."""
        return self._mcp_session_id

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for Streamable HTTP."""
        headers = {
            CONTENT_TYPE: JSON_CONTENT_TYPE,
            # Must accept both JSON and SSE per MCP spec
            ACCEPT: f"{JSON_CONTENT_TYPE}, {SSE_CONTENT_TYPE}",
        }
        # Add session ID if we have one
        if self._mcp_session_id:
            headers[MCP_SESSION_ID] = self._mcp_session_id
        # Add protocol version if negotiated
        if self._protocol_version:
            headers[MCP_PROTOCOL_VERSION] = self._protocol_version
        # Add auth headers if configured
        self._apply_auth_headers(headers)
        return headers

    def _apply_auth_headers(self, headers: dict[str, str]) -> None:
        """Apply authentication headers based on auth config."""
        if self._auth_config is None:
            return

        auth_type = self._auth_config.type.value

        if auth_type == "bearer":
            token = self._auth_config.token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.debug("Applied bearer auth header")

        elif auth_type == "api_key":
            key = self._auth_config.key
            header_name = self._auth_config.header or "X-API-Key"
            if key:
                headers[header_name] = key
                logger.debug(f"Applied API key auth header: {header_name}")

        elif auth_type == "basic":
            username = self._auth_config.username
            password = self._auth_config.password
            if username and password:
                credentials = base64.b64encode(
                    f"{username}:{password}".encode()
                ).decode("ascii")
                headers["Authorization"] = f"Basic {credentials}"
                logger.debug("Applied basic auth header")

    async def connect(self) -> None:
        """Create the HTTP session."""
        if self._session is None:
            # Create session without default headers - we'll set them per-request
            self._session = aiohttp.ClientSession()
        self._connected = True

    async def disconnect(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
        self._mcp_session_id = None
        self._protocol_version = None

    def _extract_session_id(self, response: aiohttp.ClientResponse) -> None:
        """Extract and store session ID from response headers."""
        session_id = response.headers.get(MCP_SESSION_ID)
        if session_id:
            if self._mcp_session_id != session_id:
                logger.info(f"MCP session ID: {session_id}")
            self._mcp_session_id = session_id

    def _extract_protocol_version(self, result: dict[str, Any]) -> None:
        """Extract protocol version from initialize response."""
        if "protocolVersion" in result:
            self._protocol_version = str(result["protocolVersion"])
            logger.info(f"MCP protocol version: {self._protocol_version}")

    async def _parse_sse_response(self, response: aiohttp.ClientResponse) -> MCPResponse:
        """Parse an SSE response stream and return the final result."""
        messages: list[dict[str, Any]] = []
        
        async for line in response.content:
            line = line.decode("utf-8").strip()
            
            if not line:
                continue
            
            # SSE format: "data: {json}"
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if not data_str:
                    continue
                    
                try:
                    data = json.loads(data_str)
                    messages.append(data)
                    
                    # Check if this is a response or error (end of stream for this request)
                    if "result" in data or "error" in data:
                        # This is the final response
                        return MCPResponse.from_jsonrpc(data)
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse SSE data: {e}")
                    continue
            
            # Handle event type lines
            elif line.startswith("event:"):
                event_type = line[6:].strip()
                logger.debug(f"SSE event type: {event_type}")
        
        # If we got here without a response, check if we have any messages
        if messages:
            # Return the last message as the response
            return MCPResponse.from_jsonrpc(messages[-1])
        
        return MCPResponse.from_error(
            MCPError.connection_error("SSE stream ended without a response")
        )

    async def send(self, request: MCPRequest, timeout_ms: int = 30000) -> MCPResponse:
        """
        Send a JSON-RPC request over Streamable HTTP.
        
        Args:
            request: The MCP request to send
            timeout_ms: Timeout in milliseconds
            
        Returns:
            MCPResponse with result or error
        """
        if not self.is_connected:
            return MCPResponse.from_error(
                MCPError.connection_error("Transport not connected. Call connect() first.")
            )

        timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
        payload = request.to_dict()
        headers = self._build_headers()
        
        is_initialize = request.method == "initialize"

        try:
            async with self._session.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=timeout,
            ) as resp:
                # Extract session ID from response
                self._extract_session_id(resp)
                
                # Check HTTP status - accept 200 and 202
                if resp.status not in (200, 202):
                    text = await resp.text()
                    return MCPResponse.from_error(
                        MCPError.connection_error(
                            f"HTTP {resp.status}: {resp.reason}",
                            data={"body": text[:500]},
                        )
                    )

                # Determine response type from Content-Type header
                content_type = resp.headers.get(CONTENT_TYPE, "").lower()
                
                if SSE_CONTENT_TYPE in content_type:
                    # Handle SSE streaming response
                    logger.debug("Received SSE response")
                    response = await self._parse_sse_response(resp)
                else:
                    # Handle regular JSON response
                    try:
                        data = await resp.json()
                    except json.JSONDecodeError as e:
                        text = await resp.text()
                        return MCPResponse.from_error(
                            MCPError(
                                code=-32700,
                                message=f"Invalid JSON response: {e}",
                                data={"body": text[:500]},
                            )
                        )
                    response = MCPResponse.from_jsonrpc(data)

                # Extract protocol version from initialize response
                if is_initialize and response.result:
                    self._extract_protocol_version(response.result)

                return response

        except asyncio.TimeoutError:
            return MCPResponse.from_error(
                MCPError.timeout_error(
                    f"Request timed out after {timeout_ms}ms",
                    data={"url": self.url, "method": request.method},
                )
            )
        except aiohttp.ClientConnectorError as e:
            return MCPResponse.from_error(
                MCPError.connection_error(
                    f"Connection failed: {e}",
                    data={"url": self.url},
                )
            )
        except aiohttp.ClientError as e:
            return MCPResponse.from_error(
                MCPError.connection_error(
                    f"HTTP error: {e}",
                    data={"url": self.url},
                )
            )
        except Exception as e:
            return MCPResponse.from_error(
                MCPError(
                    code=-32603,
                    message=f"Unexpected error: {type(e).__name__}: {e}",
                )
            )

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        session = f", session={self._mcp_session_id}" if self._mcp_session_id else ""
        return f"StreamableHTTPTransport(url={self.url!r}, status={status}{session})"


# Alias for backward compatibility
HTTPTransport = StreamableHTTPTransport
