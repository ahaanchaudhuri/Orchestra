"""
Schema parser for MCP test collections.

This module converts validated YAML data into typed Collection structures.
"""

from __future__ import annotations

import re
from typing import Any

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


class SchemaParser:
    """Parses and converts validated YAML to typed Collection structure."""

    # Regex for template interpolation: {{env.KEY}} or {{steps.id.path}}
    TEMPLATE_PATTERN = re.compile(r"\{\{([^}]+)\}\}")

    def __init__(self, data: dict[str, Any]):
        self.data = data

    def parse(self) -> Collection:
        """Convert validated data to typed Collection."""
        return Collection(
            version=self.data["version"],
            name=self.data["name"],
            server=self._parse_server(),
            env=self.data.get("env", {}),
            defaults=self._parse_defaults(),
            steps=self._parse_steps(),
        )

    def _parse_server(self) -> ServerConfig:
        server = self.data["server"]
        transport = TransportType(server["transport"])

        return ServerConfig(
            transport=transport,
            url=server.get("url"),
            command=server.get("command"),
            args=server.get("args", []),
            auth=self._parse_auth(server.get("auth")),
            env=server.get("env", {}),
        )

    def _parse_auth(self, auth_data: dict | None) -> AuthConfig | None:
        """Parse auth configuration if present."""
        if auth_data is None:
            return None

        auth_type = AuthType(auth_data["type"])

        return AuthConfig(
            type=auth_type,
            token=auth_data.get("token"),
            header=auth_data.get("header", "X-API-Key"),
            key=auth_data.get("key"),
            username=auth_data.get("username"),
            password=auth_data.get("password"),
        )

    def _parse_defaults(self) -> Defaults:
        defaults = self.data.get("defaults", {})
        return Defaults(
            timeout_ms=defaults.get("timeout_ms", 30000),
            retries=defaults.get("retries", 0),
        )

    def _parse_steps(self) -> list[Step]:
        steps: list[Step] = []
        for step in self.data.get("steps", []):
            if step["type"] == "tool_call":
                steps.append(self._parse_tool_call(step))
            elif step["type"] == "assert":
                steps.append(self._parse_assert(step))
        return steps

    def _parse_tool_call(self, step: dict) -> ToolCallStep:
        return ToolCallStep(
            id=step["id"],
            type=StepType.TOOL_CALL,
            tool=step["tool"],
            input=step.get("input", {}),
            save=step.get("save"),
            delay_ms=step.get("delay_ms"),
        )

    def _parse_assert(self, step: dict) -> AssertStep:
        check_data = step["check"]
        check = AssertCheck(
            op=AssertOp(check_data["op"]),
            path=check_data.get("path", "$"),  # Default to root for ops that don't need path
            value=check_data.get("value"),
        )
        return AssertStep(
            id=step["id"],
            type=StepType.ASSERT,
            from_step=step["from"],
            check=check,
            delay_ms=step.get("delay_ms"),
        )
