"""
Schema validation for MCP test collections.

This module contains the validation logic that checks raw parsed YAML
against the collection schema and reports errors with helpful messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AssertOp, AuthType, StepType, TransportType


# ─────────────────────────────────────────────────────────────────────────────
# Validation Result Types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationError:
    """Represents a single validation error with context."""
    path: str  # e.g., "steps[0].input.query"
    message: str
    value: Any = None
    suggestion: str | None = None

    def __str__(self) -> str:
        parts = [f"❌ {self.path}: {self.message}"]
        if self.value is not None:
            parts.append(f"   Got: {repr(self.value)}")
        if self.suggestion:
            parts.append(f"   💡 {self.suggestion}")
        return "\n".join(parts)


@dataclass
class ValidationResult:
    """Result of schema validation."""
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(
        self,
        path: str,
        message: str,
        value: Any = None,
        suggestion: str | None = None
    ) -> None:
        self.errors.append(ValidationError(path, message, value, suggestion))

    def __str__(self) -> str:
        if self.is_valid:
            return "✅ Schema validation passed"
        lines = [f"Schema validation failed with {len(self.errors)} error(s):\n"]
        lines.extend(str(e) for e in self.errors)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Schema Validator
# ─────────────────────────────────────────────────────────────────────────────

class SchemaValidator:
    """Validates raw parsed YAML against the collection schema."""

    REQUIRED_TOP_LEVEL = {"version", "name", "server", "steps"}
    OPTIONAL_TOP_LEVEL = {"env", "defaults"}
    VALID_STEP_TYPES = {t.value for t in StepType}
    VALID_ASSERT_OPS = {op.value for op in AssertOp}
    VALID_TRANSPORTS = {t.value for t in TransportType}
    VALID_AUTH_TYPES = {t.value for t in AuthType}

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.result = ValidationResult()
        self.step_ids: set[str] = set()

    def validate(self) -> ValidationResult:
        """Run all validation checks and return result."""
        self._validate_top_level()
        if not self.result.is_valid:
            return self.result

        self._validate_version()
        self._validate_name()
        self._validate_server()
        self._validate_env()
        self._validate_defaults()
        self._validate_steps()

        return self.result

    def _validate_top_level(self) -> None:
        """Check required and unknown top-level keys."""
        keys = set(self.data.keys())
        missing = self.REQUIRED_TOP_LEVEL - keys
        unknown = keys - self.REQUIRED_TOP_LEVEL - self.OPTIONAL_TOP_LEVEL

        for key in missing:
            self.result.add_error(
                key,
                f"Required field '{key}' is missing",
                suggestion=f"Add '{key}:' to your collection file"
            )

        for key in unknown:
            self.result.add_error(
                key,
                f"Unknown top-level field '{key}'",
                suggestion=f"Valid fields are: {', '.join(sorted(self.REQUIRED_TOP_LEVEL | self.OPTIONAL_TOP_LEVEL))}"
            )

    def _validate_version(self) -> None:
        version = self.data.get("version")
        if not isinstance(version, int):
            self.result.add_error(
                "version",
                "Must be an integer",
                value=version,
                suggestion="Use 'version: 1'"
            )
        elif version < 1:
            self.result.add_error(
                "version",
                "Must be >= 1",
                value=version
            )

    def _validate_name(self) -> None:
        name = self.data.get("name")
        if not isinstance(name, str):
            self.result.add_error(
                "name",
                "Must be a string",
                value=name
            )
        elif not name.strip():
            self.result.add_error(
                "name",
                "Cannot be empty",
                suggestion="Provide a descriptive name for your collection"
            )

    def _validate_server(self) -> None:
        server = self.data.get("server")
        if not isinstance(server, dict):
            self.result.add_error(
                "server",
                "Must be an object",
                value=server
            )
            return

        transport = server.get("transport")
        if transport not in self.VALID_TRANSPORTS:
            self.result.add_error(
                "server.transport",
                "Invalid transport type",
                value=transport,
                suggestion=f"Valid transports: {', '.join(sorted(self.VALID_TRANSPORTS))}"
            )
            return

        if transport == "http":
            url = server.get("url")
            if not url:
                self.result.add_error(
                    "server.url",
                    "Required when transport is 'http'",
                    suggestion="Add 'url: \"http://...\"' to server config"
                )
            elif not isinstance(url, str):
                self.result.add_error(
                    "server.url",
                    "Must be a string",
                    value=url
                )
            elif not (url.startswith("http://") or url.startswith("https://")):
                self.result.add_error(
                    "server.url",
                    "Must be a valid HTTP(S) URL",
                    value=url,
                    suggestion="URL should start with 'http://' or 'https://'"
                )
            
            # Validate auth if present
            auth = server.get("auth")
            if auth is not None:
                self._validate_auth(auth)

        elif transport == "stdio":
            command = server.get("command")
            if not command:
                self.result.add_error(
                    "server.command",
                    "Required when transport is 'stdio'",
                    suggestion="Add 'command: \"path/to/executable\"' to server config"
                )

        elif transport == "sse":
            url = server.get("url")
            if not url:
                self.result.add_error(
                    "server.url",
                    "Required when transport is 'sse'",
                    suggestion="Add 'url: \"http://localhost:3001\"' to server config"
                )
            elif not isinstance(url, str):
                self.result.add_error(
                    "server.url",
                    "Must be a string",
                    value=url
                )
            elif not (url.startswith("http://") or url.startswith("https://")):
                self.result.add_error(
                    "server.url",
                    "Must be a valid HTTP(S) URL",
                    value=url,
                    suggestion="URL should start with 'http://' or 'https://'"
                )

            # Validate auth if present
            auth = server.get("auth")
            if auth is not None:
                self._validate_auth(auth)

    def _validate_env(self) -> None:
        env = self.data.get("env")
        if env is None:
            return
        if not isinstance(env, dict):
            self.result.add_error(
                "env",
                "Must be an object (key-value pairs)",
                value=env
            )

    def _validate_defaults(self) -> None:
        defaults = self.data.get("defaults")
        if defaults is None:
            return
        if not isinstance(defaults, dict):
            self.result.add_error(
                "defaults",
                "Must be an object",
                value=defaults
            )
            return

        timeout = defaults.get("timeout_ms")
        if timeout is not None:
            if not isinstance(timeout, int) or timeout < 0:
                self.result.add_error(
                    "defaults.timeout_ms",
                    "Must be a non-negative integer (milliseconds)",
                    value=timeout
                )

        retries = defaults.get("retries")
        if retries is not None:
            if not isinstance(retries, int) or retries < 0:
                self.result.add_error(
                    "defaults.retries",
                    "Must be a non-negative integer",
                    value=retries
                )

    def _validate_steps(self) -> None:
        steps = self.data.get("steps")
        if not isinstance(steps, list):
            self.result.add_error(
                "steps",
                "Must be a list",
                value=steps
            )
            return

        if len(steps) == 0:
            self.result.add_error(
                "steps",
                "Must contain at least one step",
                suggestion="Add at least one tool_call or assert step"
            )
            return

        for i, step in enumerate(steps):
            self._validate_step(i, step)

    def _validate_step(self, index: int, step: Any) -> None:
        path = f"steps[{index}]"

        if not isinstance(step, dict):
            self.result.add_error(
                path,
                "Step must be an object",
                value=step
            )
            return

        # Check required fields
        step_id = step.get("id")
        if not step_id:
            self.result.add_error(
                f"{path}.id",
                "Step must have an 'id' field",
                suggestion="Add a unique identifier like 'id: my_step'"
            )
        elif not isinstance(step_id, str):
            self.result.add_error(
                f"{path}.id",
                "Step id must be a string",
                value=step_id
            )
        elif step_id in self.step_ids:
            self.result.add_error(
                f"{path}.id",
                "Duplicate step id",
                value=step_id,
                suggestion="Each step must have a unique id"
            )
        else:
            self.step_ids.add(step_id)

        step_type = step.get("type")
        if step_type not in self.VALID_STEP_TYPES:
            self.result.add_error(
                f"{path}.type",
                "Invalid step type",
                value=step_type,
                suggestion=f"Valid types: {', '.join(sorted(self.VALID_STEP_TYPES))}"
            )
            return

        if step_type == "tool_call":
            self._validate_tool_call_step(path, step)
        elif step_type == "assert":
            self._validate_assert_step(path, step)

    def _validate_tool_call_step(self, path: str, step: dict) -> None:
        tool = step.get("tool")
        if not tool:
            self.result.add_error(
                f"{path}.tool",
                "tool_call step requires a 'tool' field",
                suggestion="Specify the MCP tool name to call"
            )
        elif not isinstance(tool, str):
            self.result.add_error(
                f"{path}.tool",
                "Tool name must be a string",
                value=tool
            )

        input_data = step.get("input")
        if input_data is not None and not isinstance(input_data, dict):
            self.result.add_error(
                f"{path}.input",
                "Input must be an object",
                value=input_data
            )

        save = step.get("save")
        if save is not None and not isinstance(save, str):
            self.result.add_error(
                f"{path}.save",
                "Save must be a string (JSONPath expression)",
                value=save
            )

    def _validate_assert_step(self, path: str, step: dict) -> None:
        from_step = step.get("from")
        if not from_step:
            self.result.add_error(
                f"{path}.from",
                "assert step requires a 'from' field",
                suggestion="Specify which step's output to assert on"
            )
        elif not isinstance(from_step, str):
            self.result.add_error(
                f"{path}.from",
                "'from' must be a string (step id)",
                value=from_step
            )
        elif from_step not in self.step_ids:
            self.result.add_error(
                f"{path}.from",
                "References unknown step",
                value=from_step,
                suggestion=f"Available steps: {', '.join(sorted(self.step_ids)) or '(none yet)'}"
            )

        check = step.get("check")
        if not check:
            self.result.add_error(
                f"{path}.check",
                "assert step requires a 'check' field"
            )
            return
        if not isinstance(check, dict):
            self.result.add_error(
                f"{path}.check",
                "Check must be an object",
                value=check
            )
            return

        op = check.get("op")
        if op not in self.VALID_ASSERT_OPS:
            self.result.add_error(
                f"{path}.check.op",
                "Invalid assertion operator",
                value=op,
                suggestion=f"Valid operators: {', '.join(sorted(self.VALID_ASSERT_OPS))}"
            )

        # Some operators don't require a path (they check the root object)
        path_not_required_ops = {"is_error", "no_error"}
        
        check_path = check.get("path")
        if not check_path and op not in path_not_required_ops:
            self.result.add_error(
                f"{path}.check.path",
                "Check requires a 'path' field (JSONPath expression)"
            )
        elif check_path and not isinstance(check_path, str):
            self.result.add_error(
                f"{path}.check.path",
                "Path must be a string",
                value=check_path
            )

        # Some ops require a value
        value_required_ops = {
            "jsonpath_len_gte",
            "jsonpath_len_lte",
            "jsonpath_len_eq",
            "jsonpath_eq",
            "jsonpath_contains",
        }
        if op in value_required_ops and "value" not in check:
            self.result.add_error(
                f"{path}.check.value",
                f"Operator '{op}' requires a 'value' field"
            )

    def _validate_auth(self, auth: Any) -> None:
        """Validate auth configuration for HTTP transport."""
        if not isinstance(auth, dict):
            self.result.add_error(
                "server.auth",
                "Must be an object",
                value=auth
            )
            return

        auth_type = auth.get("type")
        if auth_type not in self.VALID_AUTH_TYPES:
            self.result.add_error(
                "server.auth.type",
                "Invalid auth type",
                value=auth_type,
                suggestion=f"Valid types: {', '.join(sorted(self.VALID_AUTH_TYPES))}"
            )
            return

        if auth_type == "bearer":
            token = auth.get("token")
            if not token:
                self.result.add_error(
                    "server.auth.token",
                    "Required for bearer auth",
                    suggestion="Add 'token: \"your-token\"' or 'token: \"{{env.TOKEN}}\"'"
                )
            elif not isinstance(token, str):
                self.result.add_error(
                    "server.auth.token",
                    "Must be a string",
                    value=token
                )

        elif auth_type == "api_key":
            key = auth.get("key")
            if not key:
                self.result.add_error(
                    "server.auth.key",
                    "Required for api_key auth",
                    suggestion="Add 'key: \"your-api-key\"' or 'key: \"{{env.API_KEY}}\"'"
                )
            elif not isinstance(key, str):
                self.result.add_error(
                    "server.auth.key",
                    "Must be a string",
                    value=key
                )
            
            header = auth.get("header")
            if header is not None and not isinstance(header, str):
                self.result.add_error(
                    "server.auth.header",
                    "Must be a string",
                    value=header,
                    suggestion="Default is 'X-API-Key'"
                )

        elif auth_type == "basic":
            username = auth.get("username")
            password = auth.get("password")
            
            if not username:
                self.result.add_error(
                    "server.auth.username",
                    "Required for basic auth",
                    suggestion="Add 'username: \"user\"' or 'username: \"{{env.USER}}\"'"
                )
            elif not isinstance(username, str):
                self.result.add_error(
                    "server.auth.username",
                    "Must be a string",
                    value=username
                )
            
            if not password:
                self.result.add_error(
                    "server.auth.password",
                    "Required for basic auth",
                    suggestion="Add 'password: \"pass\"' or 'password: \"{{env.PASS}}\"'"
                )
            elif not isinstance(password, str):
                self.result.add_error(
                    "server.auth.password",
                    "Must be a string",
                    value=password
                )

