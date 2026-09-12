# SGraph MCP Server

[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/softagram/sgraph-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/softagram/sgraph-mcp-server/actions/workflows/ci.yml)

An [MCP](https://modelcontextprotocol.io/) server that gives AI agents instant access to software architecture, dependencies, and impact analysis through pre-computed [sgraph](https://github.com/softagram/sgraph) models. One tool call replaces dozens of grep/read cycles.

## Why?

AI agents discover code structure by reading files one at a time. For a question like *"what calls this function?"*, that means grep, read, grep again, read again... Dozens of round-trips, thousands of tokens, and results that still miss indirect callers.

SGraph pre-computes the full dependency graph. The same question takes **one call** and returns **every caller** with type information.

| | Traditional (grep/read) | SGraph MCP |
|---|---|---|
| "What calls this function?" | Multiple grep + read cycles | `sgraph_get_element_dependencies` |
| "What breaks if I change this?" | Manual trace, easy to miss | `sgraph_analyze_change_impact` |
| "Show module structure" | ls + read + scroll | `sgraph_get_element_structure` |
| Time per query | Seconds (many round-trips) | Milliseconds (cached) |
| Accuracy | Text matching (noisy) | Semantic graph (precise) |

## Quick Start

### 1. Install

```bash
git clone https://github.com/softagram/sgraph-mcp-server.git
cd sgraph-mcp-server
uv sync
```

### 2. Start the server

```bash
# With Claude Code profile (recommended)
uv run python -m src.server --profile claude-code

# With a startup model (skip the load_model step; parsed on first use, not at startup)
uv run python -m src.server --profile claude-code \
  --auto-load /path/to/model.xml.zip \
  --default-scope /Project/src
```

### 3. Connect your AI agent

<details>
<summary><strong>Claude Code / Cursor (.mcp.json)</strong></summary>

Create `.mcp.json` in your project root:
```json
{
  "mcpServers": {
    "sgraph": {
      "command": "uv",
      "args": [
        "run", "--directory", "/path/to/sgraph-mcp-server",
        "python", "-m", "src.server",
        "--profile", "claude-code",
        "--transport", "stdio",
        "--auto-load", "/path/to/model.xml.zip"
      ]
    }
  }
}
```

</details>

<details>
<summary><strong>Alternative: SSE transport (any MCP client, via <code>mcp-remote</code>)</strong></summary>

Stdio is the recommended transport for local use — no port, no bridge, direct IPC. SSE is available for clients that can only speak HTTP or when you want to share one long-running server across multiple clients.

Start the server in SSE mode:
```bash
uv run python -m src.server --profile claude-code --transport sse --port 8008
```

Then connect any MCP client via the [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge:
```json
{
  "mcpServers": {
    "sgraph": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8008/sse"]
    }
  }
}
```

</details>

<details>
<summary><strong>Where do sgraph models come from?</strong></summary>

sgraph models (`.xml.zip` files) are produced by [Softagram](https://www.softagram.com/) code analysis or the open-source [sgraph CLI tools](https://github.com/softagram/sgraph).

The models represent your codebase as a hierarchical graph:
```
/Project
  /Project/src
    /Project/src/auth/login.py
      /Project/src/auth/login.py/LoginHandler        (class)
        /Project/src/auth/login.py/LoginHandler/validate  (method)
  /Project/External
    /Project/External/Python/requests                 (third-party)
```

Each element can have **associations** (dependencies) to other elements, forming a complete dependency graph.

</details>

## Tools

The **claude-code** profile provides 6 tools optimized for AI-assisted development:

| Tool | What it does | When to use |
|------|-------------|-------------|
| `sgraph_search_elements` | Find symbols by pattern | "Where is the UserService class?" |
| `sgraph_get_element_dependencies` | Query incoming/outgoing deps | "What calls this function?" |
| `sgraph_get_element_structure` | Explore hierarchy | "What's inside this module?" |
| `sgraph_analyze_change_impact` | Multi-level impact analysis | "What breaks if I change this?" |
| `sgraph_audit` | Architectural health checks | "Any circular dependencies?" |
| `sgraph_security_audit` | Security posture overview | "Any exposed secrets or CVEs?" |

The key tool is **`sgraph_get_element_dependencies`** with its `result_level` parameter for controlling abstraction:

```
result_level=None  ->  /Project/src/auth/login.py/LoginHandler/validate  (raw)
result_level=4     ->  /Project/src/auth/login.py                        (file)
result_level=3     ->  /Project/src/auth                                 (directory)
result_level=2     ->  /Project/src                                      (component)
```

For the full tool reference with workflows and examples, see **[SGRAPH_FOR_CLAUDE_CODE.md](SGRAPH_FOR_CLAUDE_CODE.md)**.

<details>
<summary><strong>Legacy profile (14 tools)</strong></summary>

The `legacy` profile provides the full original tool set for backwards compatibility:

**Basic Operations:**
`sgraph_load_model`, `sgraph_get_root_element`, `sgraph_get_element`,
`sgraph_get_element_incoming_associations`, `sgraph_get_element_outgoing_associations`

**Search:** `sgraph_search_elements_by_name`, `sgraph_get_elements_by_type`,
`sgraph_search_elements_by_attributes`

**Analysis:** `sgraph_get_subtree_dependencies`, `sgraph_get_dependency_chain`,
`sgraph_get_multiple_elements`, `sgraph_get_model_overview`,
`sgraph_get_high_level_dependencies`

```bash
uv run python -m src.server --profile legacy
```

</details>

## Example Conversation

```
You: "What would break if I rename the validate() method in auth/login.py?"

Agent calls: sgraph_analyze_change_impact(element_path="/Project/src/auth/login.py/LoginHandler/validate")

Result:
  5 callers in 3 files
  - /Project/src/api/routes.py (2 call sites)
  - /Project/src/middleware/auth.py (2 call sites)
  - /Project/tests/test_auth.py (1 call site)
  Warning: bidirectional dependency with /Project/src/middleware
```

## Architecture

```
MCP Client Request
       |
[Tools Layer]     src/tools/        -- MCP tool definitions, input validation
       |
[Services Layer]  src/services/     -- Business logic (search, deps, security)
       |
[Core Layer]      src/core/         -- Model management, data conversion
       |
[SGraph Library]                    -- Graph operations (sgraph package)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed design.

## Development

```bash
# Run tests
uv run python tests/run_all_tests.py
uv run python tests/run_all_tests.py unit          # Unit only
uv run python tests/run_all_tests.py integration   # Integration only

# Lint
uv run ruff check src/

# Run a single test file
uv run python -m pytest tests/unit/test_collect_deps.py -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

## About

Built by [Softagram](https://www.softagram.com/) using the open-source [sgraph](https://github.com/softagram/sgraph) library. Licensed under [MIT](LICENSE).
