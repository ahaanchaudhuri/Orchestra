"""
Orchestra - MCP Server Testing and Orchestration Tool

This package provides components for testing and automating MCP server interactions.

Subpackages:
    - schema_parsing: Parse and validate collection YAML files
    - transport: MCP transport layer (HTTP, STDIO)
    - assertions: Assertion engine for response validation
    - reporting: Run reports and result tracking

Usage:
    from orchestra import load_collection, create_transport, AssertionEngine, Reporter

    collection, result = load_collection("schemas/collection.yaml")
    transport = create_transport(collection.server)
    reporter = Reporter.from_collection(collection)
    
    async with transport:
        response = await transport.call_tool(ToolCallRequest(...))
        
    # Validate response
    engine = AssertionEngine()
    result = engine.exists(response.result, "$.content[0]")
    
    # Generate report
    report = reporter.finish_run()
    print(report.summary())
"""

__version__ = "0.1.0"
__author__ = "Ahaan Chaudhuri"

# Re-export schema_parsing for convenience
from .schema_parsing import (
    # Loader functions
    load_collection,
    validate_collection_yaml,
    # Models
    Collection,
    ServerConfig,
    Defaults,
    Step,
    ToolCallStep,
    AssertStep,
    AssertCheck,
    StepType,
    AssertOp,
    TransportType,
    AuthConfig,
    AuthType,
    # Validation
    ValidationResult,
    ValidationError,
    SchemaValidator,
)

# Re-export transport for convenience
from .transport import (
    # Factory
    create_transport,
    # Base
    BaseTransport,
    # Implementations
    HTTPTransport,
    STDIOTransport,
    # Models
    MCPError,
    MCPErrorCode,
    MCPRequest,
    MCPResponse,
    ToolCallRequest,
)

# Re-export assertions for convenience
from .assertions import (
    # Models
    AssertionResult,
    AssertionStatus,
    # Engine
    AssertionEngine,
    # Convenience functions
    assert_path_exists,
    assert_equals,
    assert_contains,
    assert_length_gte,
)

# Re-export reporting for convenience
from .reporting import (
    # Models
    RunReport,
    RunStatus,
    StepRecord,
    StepStatus,
    compute_collection_hash,
    # Reporter
    Reporter,
)

__all__ = [
    # Package info
    "__version__",
    "__author__",
    # Schema parsing - Loader functions
    "load_collection",
    "validate_collection_yaml",
    # Schema parsing - Models
    "Collection",
    "ServerConfig",
    "Defaults",
    "Step",
    "ToolCallStep",
    "AssertStep",
    "AssertCheck",
    "StepType",
    "AssertOp",
    "TransportType",
    "AuthConfig",
    "AuthType",
    # Schema parsing - Validation
    "ValidationResult",
    "ValidationError",
    "SchemaValidator",
    # Transport - Factory
    "create_transport",
    # Transport - Base
    "BaseTransport",
    # Transport - Implementations
    "HTTPTransport",
    "STDIOTransport",
    # Transport - Models
    "MCPError",
    "MCPErrorCode",
    "MCPRequest",
    "MCPResponse",
    "ToolCallRequest",
    # Assertions - Models
    "AssertionResult",
    "AssertionStatus",
    # Assertions - Engine
    "AssertionEngine",
    # Assertions - Convenience functions
    "assert_path_exists",
    "assert_equals",
    "assert_contains",
    "assert_length_gte",
    # Reporting - Models
    "RunReport",
    "RunStatus",
    "StepRecord",
    "StepStatus",
    "compute_collection_hash",
    # Reporting - Reporter
    "Reporter",
]
