# 🎵 Orchestra

**MCP Server Testing and Orchestration Tool**

Orchestra lets you test MCP (Model Context Protocol) servers with declarative YAML collections. Define your test steps, run tool calls, and assert on the results.

## Features

- **Declarative YAML** — Define test collections in easy-to-read YAML files
- **Multiple Transports** — Supports STDIO and Streamable HTTP connections
- **JSONPath Assertions** — Validate responses with powerful JSONPath queries
- **Authentication** — Built-in support for Bearer, API Key, and Basic auth
- **Detailed Reports** — JSON reports with run IDs, timestamps, and step details
- **CI/CD Ready** — Exit codes for pass/fail, quiet mode for automation

## Installation

```bash
# From source
pip install -e .

# Or with uv
uv pip install -e .
```

## Quick Start

### 1. Create a test collection

```yaml
# schemas/my_test.yaml
name: "My MCP Test"
description: "Test my MCP server"

server:
  transport: stdio
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-memory"]

steps:
  - id: create_entity
    type: tool_call
    tool: "create_entities"
    input:
      entities:
        - name: "TestUser"
          entityType: "person"
          observations: ["Loves testing"]
    save: "$"

  - id: verify_created
    type: assert
    from: "create_entity"
    check:
      op: "jsonpath_exists"
      path: "$[0].name"
```

### 2. Run the collection

```bash
orchestra run schemas/my_test.yaml
```

### 3. View the results

```
📄 Loading collection: schemas/my_test.yaml
   ✅ Valid collection: My MCP Test
============================================================
  Running: My MCP Test
  Server: stdio
  Steps: 2
============================================================
📡 Connecting to MCP server...
   ✅ Connected to memory-server v0.6.3

▶ Step: create_entity (tool_call)
  Tool: create_entities
  ✅ Success

▶ Step: verify_created (assert)
  Check: jsonpath_exists at $[0].name
  ✅ Passed

👋 Disconnecting...
═══════════════════════════════════════════════════════════
  Run Report: My MCP Test
  Status: ✅ PASSED
  Steps: 2 passed, 0 failed, 0 errors
═══════════════════════════════════════════════════════════
```

## CLI Reference

### `orchestra run`

Run a test collection.

```bash
orchestra run <collection.yaml> [OPTIONS]

Options:
  -V, --verbose / --no-verbose  Show detailed step output (default: on)
  -q, --quiet                   Only show errors and final status
  -r, --show-responses          Show full JSON responses from tool calls
  -o, --output [text|json]      Output format (default: text)
  -R, --report-dir PATH         Directory for JSON reports (default: reports/)
  --no-report                   Don't save a JSON report
```

### `orchestra validate`

Validate a collection without running it.

```bash
orchestra validate <collection.yaml>
```

### `orchestra info`

Show Orchestra information and version.

```bash
orchestra info
```

## Collection Schema

### Server Configuration

#### STDIO Transport

```yaml
server:
  transport: stdio
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-memory"]
```

#### HTTP Transport

```yaml
server:
  transport: http
  url: "http://localhost:8000/mcp"
```

#### With Authentication

```yaml
server:
  transport: http
  url: "https://api.example.com/mcp"
  auth:
    type: bearer
    token: "{{env.API_TOKEN}}"
```

Supported auth types: `bearer`, `api_key`, `basic`

### Steps

#### Tool Call

```yaml
- id: my_step
  type: tool_call
  tool: "tool_name"
  input:
    param1: "value"
    param2: "{{env.SOME_VAR}}"
  save: "$"  # Save result for assertions
```

#### Assertion

```yaml
- id: check_result
  type: assert
  from: "my_step"  # Reference a previous step
  check:
    op: "jsonpath_eq"
    path: "$.field"
    value: "expected"
```

### Assertion Operators

| Operator | Description | Requires Path | Requires Value |
|----------|-------------|---------------|----------------|
| `jsonpath_exists` | Check if path exists | ✅ | ❌ |
| `jsonpath_eq` | Check if value equals expected | ✅ | ✅ |
| `jsonpath_contains` | Check if string/array contains value | ✅ | ✅ |
| `jsonpath_len_eq` | Check array length equals N | ✅ | ✅ |
| `jsonpath_len_gte` | Check array length >= N | ✅ | ✅ |
| `jsonpath_len_lte` | Check array length <= N | ✅ | ✅ |
| `is_error` | Check if MCP response has isError=true | ❌ | ❌ |
| `no_error` | Check if MCP response has no error | ❌ | ❌ |

#### Error Checking

MCP servers can return successful JSON-RPC responses that contain tool execution errors (indicated by `isError: true`). Orchestra detects these and displays warnings:

```yaml
steps:
  # Call a tool that doesn't exist
  - id: bad_call
    type: tool_call
    tool: "nonexistent_tool"
    input: {}
    save: "$"
  
  # Assert that it returned an error
  - id: check_error
    type: assert
    from: "bad_call"
    check:
      op: "is_error"  # Passes if isError=true
```

Output:
```
▶ Step: bad_call (tool_call)
  Tool: nonexistent_tool
  ⚠️  Tool returned error: MCP error -32602: Tool nonexistent_tool not found

▶ Step: check_error (assert)
  Check: is_error at $
  ✅ Passed
```

### Environment Variables

Use `{{env.VAR_NAME}}` to interpolate environment variables:

```yaml
env:
  API_KEY: "my-secret-key"
  BASE_URL: "https://api.example.com"

server:
  transport: http
  url: "{{env.BASE_URL}}/mcp"
  auth:
    type: api_key
    key: "{{env.API_KEY}}"
```

## Reports

JSON reports are saved to the `reports/` directory by default:

```json
{
  "run_id": "abc123",
  "collection_name": "My Test",
  "status": "passed",
  "started_at": "2026-02-08T12:00:00Z",
  "duration_ms": 1234,
  "steps": [
    {
      "id": "create_entity",
      "type": "tool_call",
      "status": "success",
      "duration_ms": 50
    }
  ]
}
```

## License

MIT

