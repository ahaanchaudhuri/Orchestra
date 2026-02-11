"""
Transport factory for creating transports from configuration.

This module provides a factory function to create the appropriate
transport based on ServerConfig.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseTransport
from .http import HTTPTransport
from .stdio import STDIOTransport
from .sse import SSETransport

if TYPE_CHECKING:
    from ..schema_parsing import ServerConfig


def create_transport(config: ServerConfig) -> BaseTransport:
    """
    Create a transport instance from ServerConfig.
    
    Args:
        config: Server configuration from a parsed collection
        
    Returns:
        Appropriate transport instance (HTTPTransport or STDIOTransport)
        
    Raises:
        ValueError: If transport type is unsupported or config is invalid
        
    Example:
        from components.schema_parsing import load_collection
        from components.transport import create_transport
        
        collection, _ = load_collection("collection.yaml")
        transport = create_transport(collection.server)
        
        async with transport:
            response = await transport.call_tool(...)
    """
    from ..schema_parsing import TransportType
    
    if config.transport == TransportType.HTTP:
        if not config.url:
            raise ValueError("HTTP transport requires a 'url' in server config")
        return HTTPTransport(url=config.url, auth_config=config.auth)

    elif config.transport == TransportType.STDIO:
        if not config.command:
            raise ValueError("STDIO transport requires a 'command' in server config")
        return STDIOTransport(
            command=config.command,
            args=config.args,
        )

    elif config.transport == TransportType.SSE:
        if not config.url:
            raise ValueError("SSE transport requires a 'url' in server config")
        return SSETransport(
            base_url=config.url,
            auth_config=config.auth,
        )

    else:
        raise ValueError(f"Unsupported transport type: {config.transport}")

