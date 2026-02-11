"""
SSE (Server-Sent Events) transport for MCP communication.

This module implements the standard MCP SSE transport pattern:
- GET /sse - Establishes SSE connection, receives endpoint URL
- POST to endpoint - Sends JSON-RPC messages

The SSE stream provides the message endpoint URL which is used for
all subsequent JSON-RPC communication.
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
    from ..schema_parsing.models import AuthConfig

logger = logging.getLogger(__name__)


class SSETransport(BaseTransport):
    """
    MCP SSE transport.
    
    Implements the standard MCP SSE transport:
    1. GET /sse to establish connection
    2. Receive endpoint URL from SSE 'endpoint' event
    3. POST JSON-RPC messages to that endpoint
    """

    def __init__(
        self,
        base_url: str,
        auth_config: "AuthConfig | None" = None,
    ):
        """
        Initialize SSE transport.
        
        Args:
            base_url: The MCP server base URL (e.g., "http://localhost:3001")
            auth_config: Optional authentication configuration
        """
        self.base_url = base_url.rstrip("/")
        self._auth_config = auth_config
        self._session: aiohttp.ClientSession | None = None
        self._connected = False
        
        # Connection state
        self._message_endpoint: str | None = None
        
        # For keeping SSE connection alive
        self._sse_task: asyncio.Task | None = None
        self._ready_event: asyncio.Event | None = None
        self._sse_messages: asyncio.Queue | None = None
        self._connection_error: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._message_endpoint is not None

    def _build_auth_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        headers: dict[str, str] = {}
        
        if self._auth_config is None:
            return headers

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

        return headers

    async def _sse_reader(self) -> None:
        """
        Background task that keeps the SSE connection alive and reads messages.
        
        Reads the SSE stream looking for the 'endpoint' event which provides
        the URL for posting JSON-RPC messages.
        """
        sse_url = f"{self.base_url}/sse"
        headers = self._build_auth_headers()
        headers["Accept"] = "text/event-stream"
        
        logger.info(f"Connecting to SSE endpoint: {sse_url}")
        
        try:
            async with self._session.get(
                sse_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=None),  # No timeout for SSE
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    self._connection_error = f"HTTP {response.status}: {text}"
                    logger.error(f"SSE connection failed: {self._connection_error}")
                    self._ready_event.set()
                    return
                
                logger.info("SSE connection established, reading events...")
                
                current_event_type: str | None = None
                
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    
                    if not line:
                        current_event_type = None
                        continue
                    
                    logger.debug(f"SSE: {line}")
                    
                    # Parse event type
                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        logger.debug(f"Event type: {current_event_type}")
                        continue
                    
                    # Parse data lines
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        
                        # Standard MCP: endpoint event with URL path
                        if current_event_type == "endpoint" or data_str.startswith("/"):
                            self._message_endpoint = f"{self.base_url}{data_str}"
                            logger.info(f"Got message endpoint: {self._message_endpoint}")
                            self._ready_event.set()
                            continue
                        
                        # Try to parse as JSON for response messages
                        try:
                            data = json.loads(data_str)
                            if self._sse_messages:
                                await self._sse_messages.put(data)
                        except json.JSONDecodeError:
                            logger.debug(f"Non-JSON data: {data_str}")
                            continue
                
                logger.warning("SSE stream ended unexpectedly")
                
        except asyncio.CancelledError:
            logger.info("SSE reader cancelled")
            raise
        except aiohttp.ClientError as e:
            self._connection_error = f"SSE connection error: {e}"
            logger.error(self._connection_error)
            self._ready_event.set()
        except Exception as e:
            self._connection_error = f"SSE unexpected error: {e}"
            logger.error(self._connection_error)
            self._ready_event.set()

    async def connect(self) -> None:
        """
        Establish SSE connection and get message endpoint.
        
        This starts a background task to keep the SSE stream alive.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        # Initialize synchronization primitives
        self._ready_event = asyncio.Event()
        self._sse_messages = asyncio.Queue()
        self._connection_error = None
        self._message_endpoint = None
        
        # Start SSE reader in background
        self._sse_task = asyncio.create_task(self._sse_reader())
        
        # Wait for endpoint with timeout
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            if self._sse_task:
                self._sse_task.cancel()
                try:
                    await self._sse_task
                except asyncio.CancelledError:
                    pass
            raise ConnectionError("Timeout waiting for endpoint from SSE stream")
        
        # Check if we got an error or endpoint
        if self._connection_error:
            if self._sse_task:
                self._sse_task.cancel()
                try:
                    await self._sse_task
                except asyncio.CancelledError:
                    pass
            raise ConnectionError(self._connection_error)
        
        if not self._message_endpoint:
            raise ConnectionError("Failed to get message endpoint from SSE stream")
        
        self._connected = True
        logger.info(f"SSE transport connected, endpoint: {self._message_endpoint}")

    async def disconnect(self) -> None:
        """Close the SSE connection and HTTP session."""
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None
            
        if self._session:
            await self._session.close()
            self._session = None
            
        self._message_endpoint = None
        self._connected = False
        self._ready_event = None
        self._sse_messages = None
        logger.info("SSE transport disconnected")

    async def send(self, request: MCPRequest, timeout_ms: int = 30000) -> MCPResponse:
        """
        Send a JSON-RPC request via the message endpoint.
        
        Args:
            request: The MCP request to send
            timeout_ms: Timeout in milliseconds
            
        Returns:
            MCPResponse with result or error
        """
        if not self.is_connected:
            return MCPResponse.from_error(
                MCPError.connection_error(
                    "SSE transport not connected. Call connect() first."
                )
            )

        timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
        payload = request.to_dict()
        
        headers = {
            "Content-Type": "application/json",
        }
        headers.update(self._build_auth_headers())
        
        logger.debug(f"POST {self._message_endpoint}")
        logger.debug(f"Payload: {json.dumps(payload)}")

        try:
            async with self._session.post(
                self._message_endpoint,
                json=payload,
                headers=headers,
                timeout=timeout,
            ) as resp:
                logger.debug(f"Response status: {resp.status}")
                
                # 202 Accepted means async processing - response comes via SSE
                if resp.status == 202:
                    return await self._wait_for_response(request.id, timeout_ms)
                
                # Check HTTP status
                if resp.status not in (200, 202):
                    text = await resp.text()
                    logger.error(f"POST failed: HTTP {resp.status}: {text}")
                    return MCPResponse.from_error(
                        MCPError.connection_error(
                            f"HTTP {resp.status}: {resp.reason}",
                            data={"body": text[:500]},
                        )
                    )

                # Parse JSON response
                try:
                    data = await resp.json()
                    logger.debug(f"Response data: {data}")
                except json.JSONDecodeError as e:
                    text = await resp.text()
                    return MCPResponse.from_error(
                        MCPError(
                            code=-32700,
                            message=f"Invalid JSON response: {e}",
                            data={"body": text[:500]},
                        )
                    )
                
                return MCPResponse.from_jsonrpc(data)

        except asyncio.TimeoutError:
            return MCPResponse.from_error(
                MCPError.timeout_error(
                    f"Request timed out after {timeout_ms}ms",
                    data={"url": self._message_endpoint, "method": request.method},
                )
            )
        except aiohttp.ClientConnectorError as e:
            return MCPResponse.from_error(
                MCPError.connection_error(
                    f"Connection failed: {e}",
                    data={"url": self._message_endpoint},
                )
            )
        except aiohttp.ClientError as e:
            return MCPResponse.from_error(
                MCPError.connection_error(
                    f"HTTP error: {e}",
                    data={"url": self._message_endpoint},
                )
            )
        except Exception as e:
            return MCPResponse.from_error(
                MCPError(
                    code=-32603,
                    message=f"Unexpected error: {type(e).__name__}: {e}",
                )
            )

    async def _wait_for_response(self, request_id: int, timeout_ms: int) -> MCPResponse:
        """
        Wait for a response from the SSE stream.
        
        When POST returns 202, the response comes via SSE.
        """
        try:
            deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
            
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return MCPResponse.from_error(
                        MCPError.timeout_error(f"Timeout waiting for response to request {request_id}")
                    )
                
                try:
                    msg = await asyncio.wait_for(
                        self._sse_messages.get(),
                        timeout=remaining
                    )
                    
                    # Check if this is the response we're waiting for
                    if isinstance(msg, dict):
                        if msg.get("id") == request_id:
                            return MCPResponse.from_jsonrpc(msg)
                        if "result" in msg or "error" in msg:
                            return MCPResponse.from_jsonrpc(msg)
                            
                except asyncio.TimeoutError:
                    return MCPResponse.from_error(
                        MCPError.timeout_error(f"Timeout waiting for response to request {request_id}")
                    )
                    
        except Exception as e:
            return MCPResponse.from_error(
                MCPError(
                    code=-32603,
                    message=f"Error waiting for SSE response: {e}",
                )
            )

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        endpoint = f", endpoint={self._message_endpoint}" if self._message_endpoint else ""
        return f"SSETransport(url={self.base_url!r}, status={status}{endpoint})"
