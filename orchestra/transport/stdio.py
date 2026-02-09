"""
STDIO transport for MCP communication.

This module implements MCP communication over stdin/stdout with a subprocess,
using newline-delimited JSON-RPC 2.0.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from .base import BaseTransport
from .models import MCPError, MCPRequest, MCPResponse


class STDIOTransport(BaseTransport):
    """
    MCP transport over STDIO.
    
    Spawns a subprocess and communicates via stdin/stdout using
    newline-delimited JSON-RPC 2.0 messages.
    """

    def __init__(self, command: str, args: list[str] | None = None, env: dict[str, str] | None = None):
        """
        Initialize STDIO transport.
        
        Args:
            command: The command/executable to run
            args: Optional list of command arguments
            env: Optional environment variables to pass to the subprocess
        """
        self.command = command
        self.args = args or []
        self.env = env
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int | str, asyncio.Future[MCPResponse]] = {}
        self._reader_task: asyncio.Task | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return (
            self._connected
            and self._process is not None
            and self._process.returncode is None
        )

    async def connect(self) -> None:
        """Spawn the subprocess."""
        if self._process is not None:
            return

        try:
            # Build the full command
            cmd = [self.command] + self.args

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
            )
            self._connected = True

            # Start background reader
            self._reader_task = asyncio.create_task(self._read_responses())

        except FileNotFoundError:
            raise RuntimeError(f"Command not found: {self.command}")
        except PermissionError:
            raise RuntimeError(f"Permission denied: {self.command}")
        except Exception as e:
            raise RuntimeError(f"Failed to start process: {e}")

    async def disconnect(self) -> None:
        """Terminate the subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._process:
            proc = self._process
            self._process = None  # Clear reference first
            
            try:
                # Close stdin to signal the process to exit
                if proc.stdin:
                    proc.stdin.close()
                
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, ProcessLookupError, OSError):
                    pass  # Give up, process may be zombie
            except (ProcessLookupError, asyncio.CancelledError, BrokenPipeError, ConnectionResetError, OSError):
                pass  # Already dead or interrupted

        # Cancel any pending requests
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    Exception("Transport disconnected")
                )
        self._pending.clear()
        self._connected = False

    async def _read_responses(self) -> None:
        """Background task to read responses from stdout."""
        if not self._process or not self._process.stdout:
            return

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break  # EOF

                try:
                    data = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

                # Match response to request
                request_id = data.get("id")
                if request_id in self._pending:
                    future = self._pending.pop(request_id)
                    if not future.done():
                        response = MCPResponse.from_jsonrpc(data)
                        future.set_result(response)

        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # Reader died, pending requests will timeout

    async def send(self, request: MCPRequest, timeout_ms: int = 30000) -> MCPResponse:
        """
        Send a JSON-RPC request over STDIO.
        
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

        if not self._process or not self._process.stdin:
            return MCPResponse.from_error(
                MCPError.process_error("Process stdin not available")
            )

        # Create future for response
        future: asyncio.Future[MCPResponse] = asyncio.get_event_loop().create_future()
        self._pending[request.id] = future

        try:
            # Send request as newline-delimited JSON
            payload = json.dumps(request.to_dict()) + "\n"
            self._process.stdin.write(payload.encode("utf-8"))
            await self._process.stdin.drain()

            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(
                    future,
                    timeout=timeout_ms / 1000,
                )
                return response
            except asyncio.TimeoutError:
                self._pending.pop(request.id, None)
                return MCPResponse.from_error(
                    MCPError.timeout_error(
                        f"Request timed out after {timeout_ms}ms",
                        data={"method": request.method},
                    )
                )

        except BrokenPipeError:
            self._pending.pop(request.id, None)
            return MCPResponse.from_error(
                MCPError.process_error(
                    "Process pipe broken - subprocess may have crashed",
                    data=await self._get_stderr(),
                )
            )
        except Exception as e:
            self._pending.pop(request.id, None)
            return MCPResponse.from_error(
                MCPError(
                    code=-32603,
                    message=f"Unexpected error: {type(e).__name__}: {e}",
                )
            )

    async def _get_stderr(self) -> dict[str, Any] | None:
        """Try to get stderr output for error reporting."""
        if not self._process or not self._process.stderr:
            return None
        try:
            # Non-blocking read of available stderr
            stderr = await asyncio.wait_for(
                self._process.stderr.read(4096),
                timeout=0.1,
            )
            if stderr:
                return {"stderr": stderr.decode("utf-8", errors="replace")}
        except (asyncio.TimeoutError, Exception):
            pass
        return None

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        cmd = " ".join([self.command] + self.args)
        return f"STDIOTransport(command={cmd!r}, status={status})"

