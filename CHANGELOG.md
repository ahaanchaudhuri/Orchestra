# Changelog

All notable changes to Orchestra will be documented in this file.

## [0.1.0] - 2026-02-14

### 🎉 Initial Release

#### Added

**Core Features:**
- ✅ Declarative YAML-based test collections
- ✅ Support for STDIO, HTTP (Streamable HTTP), and SSE transports
- ✅ JSONPath-based assertion engine with 8 operators
- ✅ Comprehensive CLI with `run`, `validate`, `inspect`, and `info` commands
- ✅ Detailed JSON reporting with run IDs, timestamps, and step-by-step results
- ✅ Environment variable interpolation for secure credential handling

**Server Discovery (`inspect` command):**
- 🔍 Discover available tools and their schemas from any MCP server
- 🔍 Lightweight `load_server_config()` loader for inspection (no test steps required)
- 🔍 Shows parameter names, types, descriptions, and generates example YAML

**Authentication:**
- 🔒 Bearer token authentication
- 🔒 API key authentication
- 🔒 Basic authentication (username/password)

**Assertion Operators:**
- ✅ `jsonpath_exists` - Check if path exists
- ✅ `jsonpath_eq` - Equality check
- ✅ `jsonpath_contains` - String/array containment
- ✅ `jsonpath_len_eq`, `jsonpath_len_gte`, `jsonpath_len_lte` - Length checks
- ✅ `is_error` - Detect MCP tool execution errors (isError=true)
- ✅ `no_error` - Verify successful tool execution

**Rate Limiting & Flow Control:**
- ⏱️ `delay_ms` parameter on steps to prevent API rate limiting
- ⏱️ Configurable timeouts and retries

**STDIO Transport Enhancements:**
- 🔧 Environment variable passing to subprocesses
- 🔧 Support for npx-based servers with automatic package installation

**Quality of Life:**
- 📊 `--show-responses` flag for debugging (shows full JSON responses)
- 📊 Automatic detection of MCP tool errors with warning display
- 📊 Rich console output with color-coded status
- 📊 Validation before running (catches schema errors early)

#### Tested Against

Orchestra has been validated against the following production MCP servers:

- ✅ **DeepWiki** (Remote HTTP, no-auth) - AI-powered codebase documentation
- ✅ **MCPCalc** (Remote HTTP, no-auth) - Calculator service
- ✅ **Puppeteer** (Local STDIO) - Browser automation (deprecated but functional)
- ✅ **Brave Search** (Local STDIO, API key) - Web search with rate limiting
- ✅ **Kaggle** (Local STDIO) - Dataset management
- ✅ **Memory Server** (Local STDIO) - Knowledge graph storage
- ✅ **Everything Server** (STDIO/HTTP/SSE) - Demo server with all MCP features

#### Known Limitations

- Chrome DevTools MCP times out during initialization (browser launch takes >30s)
- SSE transport tested but less common than HTTP/STDIO in the wild
- Some MCP servers using non-standard patterns may require custom handling

#### Examples

Over 20 example schemas included:
- Inspection schemas for quick server discovery
- Full test collections for real-world servers
- Pattern examples for STDIO, HTTP, SSE, authentication, and more

#### Technical Details

**Project Structure:**
- `orchestra/` - Main package
  - `cli.py` - Typer-based CLI interface
  - `schema_parsing/` - YAML schema parsing and validation
  - `transport/` - Transport layer (STDIO, HTTP, SSE)
  - `assertions/` - JSONPath assertion engine
  - `reporting/` - JSON report generation

**Dependencies:**
- `typer` - CLI framework
- `rich` - Beautiful terminal output
- `pyyaml` - YAML parsing
- `jsonpath-ng` - JSONPath queries
- `aiohttp` - Async HTTP client
- `pydantic` - Data validation

**Installation:**
```bash
pip install -e .
```

**Basic Usage:**
```bash
# Discover server tools
orchestra inspect schemas/my_server.yaml

# Run tests
orchestra run schemas/my_test.yaml

# Validate schema
orchestra validate schemas/my_test.yaml
```

---

## Future Roadmap

Potential features for future releases:

- [ ] Parallel test execution
- [ ] Test data fixtures and templating
- [ ] WebSocket transport support
- [ ] Plugin system for custom assertions
- [ ] HTML report generation
- [ ] Test coverage metrics
- [ ] Interactive test builder
- [ ] Cloud MCP server registry integration

---

For more information, see the [README](README.md).

