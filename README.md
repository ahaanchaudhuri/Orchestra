# 🎵 Orchestra

**Production-Ready MCP Server Testing and Orchestration Tool**

Orchestra is a powerful CLI tool for testing MCP (Model Context Protocol) servers with declarative YAML test collections. Discover server capabilities, write comprehensive tests, and validate your MCP implementations with ease.

## ✨ Key Features

- **🔍 Server Discovery** — `inspect` command reveals all available tools and their schemas
- **📝 Declarative YAML** — Define test collections in easy-to-read YAML files
- **🌐 Multiple Transports** — STDIO (local), HTTP (remote), and SSE support
- **🔒 Authentication** — Built-in support for Bearer, API Key, and Basic auth
- **✅ Powerful Assertions** — JSONPath queries, error detection, and content validation
- **⚡ Rate Limit Handling** — Configurable delays between steps
- **📊 Detailed Reports** — JSON reports with run IDs, timestamps, and step-by-step results
- **🚀 CI/CD Ready** — Exit codes for pass/fail, quiet mode for automation
- **🔐 Secure** — Environment variable support for secrets and API keys

## 📦 Installation

```bash
# From source
pip install -e .

# Or with uv
uv pip install -e .
```

## 🚀 Quick Start

### 1. Discover Server Capabilities (New!)

Use the `inspect` command to discover what tools a server offers:

```bash
orchestra inspect schemas/my_server.yaml
```

**Example output:**
```
📡 Connecting to MCP server...
   ✅ Connected to DeepWiki v2.14.3

🔍 Discovering tools...

Found 3 tool(s):

1. read_wiki_structure
   Get a list of documentation topics for a GitHub repository.

   Parameters:
   * repoName (string)
      GitHub repository in owner/repo format (e.g. "facebook/react")

   Example YAML:
   - id: call_read_wiki_structure
     type: tool_call
     tool: "read_wiki_structure"
     input:
       repoName: "facebook/react"
     save: "$"
```

**For inspection, you only need server config (no test steps required!):**

```yaml
# schemas/my_server.yaml
version: 1
name: "My MCP Server"

server:
  transport: "http"
  url: "https://api.example.com/mcp"
```

### 2. Create a Test Collection

```yaml
# schemas/my_test.yaml
version: 1
name: "My MCP Test"

server:
  transport: "stdio"
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
    delay_ms: 1000  # Wait 1 second before next step

  - id: verify_no_error
    type: assert
    from: "create_entity"
    check:
      op: "no_error"

  - id: verify_created
    type: assert
    from: "create_entity"
    check:
      op: "jsonpath_exists"
      path: "$.content[0].text"
```

### 3. Run the Collection

```bash
# Standard run
orchestra run schemas/my_test.yaml

# Show full JSON responses (great for debugging)
orchestra run schemas/my_test.yaml --show-responses

# Quiet mode (errors only)
orchestra run schemas/my_test.yaml --quiet
```

### 4. View the Results

```
📄 Loading collection: schemas/my_test.yaml
   ✅ Valid collection: My MCP Test

============================================================
  Running: My MCP Test
  Server: stdio
  Steps: 3
============================================================

📡 Connecting to MCP server...
   ✅ Connected to memory-server v0.6.3

▶ Step: create_entity (tool_call)
  Tool: create_entities
  Input: {"entities": [{"name": "TestUser", ...}]}...
  ✅ Success
  ⏱️  Waiting 1000ms...

▶ Step: verify_no_error (assert)
  Asserting on: create_entity
  Check: no_error at $
  ✅ Passed

▶ Step: verify_created (assert)
  Asserting on: create_entity
  Check: jsonpath_exists at $.content[0].text
  ✅ Passed

👋 Disconnecting...

═══════════════════════════════════════════════════════════
  Run Report: My MCP Test
═══════════════════════════════════════════════════════════
  Run ID:     abc123-def456
  Status:     ✅ PASSED
  Duration:   1234ms
  Started:    2026-02-14T12:00:00Z
───────────────────────────────────────────────────────────
  Steps: 3 passed, 0 failed, 0 errors, 0 skipped
───────────────────────────────────────────────────────────
  ✅  tool_call - 150ms
  ✅  assert - 2ms
  ✅  assert - 5ms
═══════════════════════════════════════════════════════════

📁 Report saved: reports/abc123-def456.json
```

## 📚 CLI Reference

### `orchestra inspect`

Discover available tools and their schemas from any MCP server.

```bash
orchestra inspect <server.yaml> [OPTIONS]

Options:
  -v, --verbose    Show detailed connection info and raw schemas
```

**Use cases:**
- Explore new MCP servers before writing tests
- Verify correct parameter names
- Generate example YAML snippets for tool calls

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

Validate a collection schema without running it.

```bash
orchestra validate <collection.yaml>
```

### `orchestra info`

Show Orchestra information and version.

```bash
orchestra info
```

## 📖 Collection Schema Reference

### Server Configuration

#### STDIO Transport (Local Servers)

For local MCP servers that run as subprocesses:

```yaml
server:
  transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-memory"]
  
  # Optional: Pass environment variables to subprocess
  env:
    API_KEY: "{{env.MY_API_KEY}}"
    DEBUG: "true"
```

**Environment Variables for STDIO:**
- Orchestra can pass environment variables from the collection schema to the subprocess
- Useful for servers that need API keys (e.g., Brave Search, Kaggle)

```yaml
# Collection-level env vars (accessible via {{env.VAR}})
env:
  BRAVE_API_KEY: "your-key-here"

server:
  transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  # Pass to subprocess
  env:
    BRAVE_API_KEY: "{{env.BRAVE_API_KEY}}"
```

#### HTTP Transport (Remote Servers)

For remote MCP servers over HTTP (Streamable HTTP):

```yaml
server:
  transport: "http"
  url: "https://mcp.deepwiki.com/mcp"
```

#### SSE Transport

For servers using Server-Sent Events:

```yaml
server:
  transport: "sse"
  url: "http://localhost:3001"
```

#### With Authentication

Orchestra supports three authentication types:

**Bearer Token:**
```yaml
server:
  transport: "http"
  url: "https://api.example.com/mcp"
  auth:
    type: "bearer"
    token: "{{env.API_TOKEN}}"
```

**API Key:**
```yaml
server:
  transport: "http"
  url: "https://api.example.com/mcp"
  auth:
    type: "api_key"
    key: "{{env.API_KEY}}"
```

**Basic Auth:**
```yaml
server:
  transport: "http"
  url: "https://api.example.com/mcp"
  auth:
    type: "basic"
    username: "{{env.USERNAME}}"
    password: "{{env.PASSWORD}}"
```

### Steps

#### Tool Call Step

Invoke an MCP tool and optionally save the result for assertions:

```yaml
- id: my_step
  type: tool_call
  tool: "tool_name"
  input:
    param1: "value"
    param2: 123
    nested:
      key: "value"
  save: "$"  # Save full response
  delay_ms: 2000  # Wait 2 seconds after this step (for rate limiting)
```

**Rate Limiting:**
Use `delay_ms` to prevent hitting rate limits on public APIs:

```yaml
steps:
  - id: search_1
    type: tool_call
    tool: "brave_web_search"
    input:
      query: "Python"
    save: "$"
    delay_ms: 2000  # Wait 2 seconds

  - id: search_2
    type: tool_call
    tool: "brave_web_search"
    input:
      query: "JavaScript"
    save: "$"
    delay_ms: 2000  # Wait 2 seconds
```

#### Assertion Step

Validate tool call results with powerful assertions:

```yaml
- id: check_result
  type: assert
  from: "my_step"  # Reference a previous step
  check:
    op: "jsonpath_eq"
    path: "$.field"
    value: "expected"
  delay_ms: 0  # Optional delay after assertion
```

### Assertion Operators

| Operator | Description | Requires Path | Requires Value | Example |
|----------|-------------|---------------|----------------|---------|
| `jsonpath_exists` | Check if path exists in response | ✅ | ❌ | Path `$.content[0].text` exists |
| `jsonpath_eq` | Check if value equals expected | ✅ | ✅ | `$.status` equals `"success"` |
| `jsonpath_contains` | Check if string/array contains value | ✅ | ✅ | `$.text` contains `"hello"` |
| `jsonpath_len_eq` | Check array length equals N | ✅ | ✅ | `$.items` has exactly 5 items |
| `jsonpath_len_gte` | Check array length >= N | ✅ | ✅ | `$.items` has at least 3 items |
| `jsonpath_len_lte` | Check array length <= N | ✅ | ✅ | `$.items` has at most 10 items |
| `is_error` | Check if MCP response has isError=true | ❌ | ❌ | Response contains an error |
| `no_error` | Check if MCP response has no error | ❌ | ❌ | Response is successful |

#### Error Detection

MCP servers can return successful JSON-RPC responses that contain tool execution errors (indicated by `isError: true`). Orchestra automatically detects these and provides specialized assertions:

```yaml
steps:
  # Call a tool that might fail
  - id: risky_call
    type: tool_call
    tool: "some_tool"
    input:
      param: "value"
    save: "$"
  
  # Verify it succeeded
  - id: check_success
    type: assert
    from: "risky_call"
    check:
      op: "no_error"  # Fails if isError=true

  # Or test error handling
  - id: bad_call
    type: tool_call
    tool: "nonexistent_tool"
    input: {}
    save: "$"
  
  - id: expect_error
    type: assert
    from: "bad_call"
    check:
      op: "is_error"  # Passes if isError=true
```

**Console output with error detection:**
```
▶ Step: bad_call (tool_call)
  Tool: nonexistent_tool
  ⚠️  Tool returned error: Tool not found
  Response:
  {
    "content": [...],
    "isError": true
  }

▶ Step: expect_error (assert)
  Check: is_error at $
  ✅ Passed
```

### Defaults

Set default values for all steps:

```yaml
defaults:
  timeout_ms: 30000  # 30 seconds (default)
  retries: 0         # No retries (default)
```

### Environment Variables

Orchestra supports environment variable interpolation using `{{env.VAR_NAME}}`:

```yaml
# Define at collection level
env:
  API_KEY: "my-secret-key"
  BASE_URL: "https://api.example.com"

server:
  transport: "http"
  url: "{{env.BASE_URL}}/mcp"
  auth:
    type: "api_key"
    key: "{{env.API_KEY}}"

steps:
  - id: call_with_env
    type: tool_call
    tool: "search"
    input:
      api_key: "{{env.API_KEY}}"
```

**Environment variables are pulled from:**
1. Collection-level `env` block
2. Shell environment (via `os.environ`)

## 🧪 Real-World Examples

### Example 1: DeepWiki (Remote HTTP, No Auth)

Test an AI-powered documentation server:

```yaml
version: 1
name: "DeepWiki Test"

server:
  transport: "http"
  url: "https://mcp.deepwiki.com/mcp"

steps:
  - id: ask_about_react
    type: tool_call
    tool: "ask_question"
    input:
      repoName: "facebook/react"
      question: "What are React hooks?"
    save: "$"
    delay_ms: 2000

  - id: check_answer
    type: assert
    from: "ask_about_react"
    check:
      op: "jsonpath_contains"
      path: "$.content[0].text"
      value: "hook"
```

### Example 2: Brave Search (STDIO, API Key)

Test a search API with authentication:

```yaml
version: 1
name: "Brave Search Test"

env:
  BRAVE_API_KEY: "your-api-key"

server:
  transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  env:
    BRAVE_API_KEY: "{{env.BRAVE_API_KEY}}"

steps:
  - id: search_python
    type: tool_call
    tool: "brave_web_search"
    input:
      query: "Python programming"
      count: 5
    save: "$"
    delay_ms: 2000  # Rate limiting

  - id: check_results
    type: assert
    from: "search_python"
    check:
      op: "jsonpath_len_gte"
      path: "$.content"
      value: 1
```

### Example 3: MCPCalc (Remote HTTP, Calculator Service)

Test a calculator service:

```yaml
version: 1
name: "MCPCalc Test"

server:
  transport: "http"
  url: "https://mcpcalc.com/api/v1/mcp"

steps:
  - id: list_calculators
    type: tool_call
    tool: "list_calculators"
    input:
      category: "math"
    save: "$"

  - id: calculate_percentage
    type: tool_call
    tool: "calculate"
    input:
      calculator: "percentage"
      inputs:
        value: 50
        percentage: 20
    save: "$"

  - id: verify_result
    type: assert
    from: "calculate_percentage"
    check:
      op: "no_error"
```

## 📊 Reports

Orchestra generates detailed JSON reports for every test run:

```json
{
  "run_id": "abc123-def456",
  "collection_name": "My Test",
  "status": "passed",
  "started_at": "2026-02-14T12:00:00Z",
  "completed_at": "2026-02-14T12:00:01Z",
  "duration_ms": 1234,
  "server": {
    "name": "memory-server",
    "version": "0.6.3"
  },
  "steps": [
    {
      "id": "create_entity",
      "type": "tool_call",
      "status": "success",
      "duration_ms": 150,
      "tool": "create_entities",
      "result": { ... }
    },
    {
      "id": "verify_created",
      "type": "assert",
      "status": "passed",
      "duration_ms": 5,
      "assertion": {
        "op": "jsonpath_exists",
        "path": "$.content[0].text"
      }
    }
  ]
}
```

## ✅ Tested MCP Servers

Orchestra has been validated against multiple production MCP servers:

- ✅ **DeepWiki** - AI-powered codebase documentation (HTTP, remote)
- ✅ **MCPCalc** - Calculator service (HTTP, remote)
- ✅ **Puppeteer** - Browser automation (STDIO, local)
- ✅ **Brave Search** - Web search API (STDIO, API key auth)
- ✅ **Kaggle** - Dataset management (STDIO, local)
- ✅ **Memory Server** - Knowledge graph storage (STDIO, local)
- ✅ **Everything Server** - Demo server with all MCP features (STDIO/HTTP/SSE)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

MIT

## 🙏 Acknowledgments

Built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) by Anthropic.

---

**Made with ❤️ for the MCP community**
