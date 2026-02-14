# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SGraph MCP Server is a Python 3.13+ MCP (Model Context Protocol) server that provides AI agents with fast access to software structure and dependency information through cached sgraph models. It reduces query time from seconds to milliseconds by pre-loading hierarchical graph models into memory.

## Development Commands

```bash
# Install dependencies
uv sync

# Run the MCP server (port 8008) - default legacy profile
uv run python -m src.server

# Run with specific profile
uv run python -m src.server --profile claude-code  # 5 optimized tools
uv run python -m src.server --profile legacy       # 14 tools (default)

# Run all tests
uv run python tests/run_all_tests.py

# Run specific test categories
uv run python tests/run_all_tests.py unit
uv run python tests/run_all_tests.py integration
uv run python tests/run_all_tests.py performance

# Run a single test file
uv run python -m pytest tests/unit/test_model_manager.py -v

# Lint with ruff
uv run ruff check src/
```

## Architecture

The project uses a layered modular architecture:

```
MCP Client Request
       ↓
[Tools Layer] src/tools/        → MCP tool definitions, input validation
       ↓
[Services Layer] src/services/  → Business logic (search, dependencies, overview)
       ↓
[Core Layer] src/core/          → Model management, data conversion
       ↓
[SGraph Library]                → Graph operations
```

### Key Components

**Core** (`src/core/`):
- `ModelManager` - Async model loading with 60s timeout, in-memory caching, nanoid-based model IDs
- `ElementConverter` - SElement to dictionary conversion

**Services** (`src/services/`): Static methods for testability
- `SearchService` - Pattern matching (regex/glob), type filtering, scoped searches
- `DependencyService` - Transitive dependency chains, subtree analysis, bulk retrieval
- `OverviewService` - Hierarchical structure generation with configurable depth

**Tools** (`src/tools/`): MCP tool implementations
- `model_tools.py` - Load model, get overview
- `search_tools.py` - Search by name/type/attributes
- `analysis_tools.py` - Dependency analysis tools
- `navigation_tools.py` - Element navigation

**Utils** (`src/utils/`):
- `validators.py` - Path security checks (blocks `..`), model ID validation (24-char nanoid)
- `logging.py` - Centralized logging config

### SGraph Data Model

Elements form a hierarchy: `/Project/<directory>/<file>/<code_element>`
- Associations are directed dependencies between elements
- External dependencies live under `/ProjectName/External`

## Testing

- **Unit tests** (`tests/unit/`) - Component isolation with mocks
- **Integration tests** (`tests/integration/`) - End-to-end workflows with real models
- **Performance tests** (`tests/performance/`) - Validates targets: <100ms searches, <150ms overviews

Test models are in `sgraph-example-models/` (e.g., `langchain.xml.zip`).

## Profiles

The server supports multiple profiles in `src/profiles/`:

| Profile | Tools | Description |
|---------|-------|-------------|
| `legacy` | 14 | Full original tool set (default, backwards compatible) |
| `claude-code` | 5 | Optimized for Claude Code - plain text TOON output, `include_descendants` support |

**Claude Code profile tools** (see `SGRAPH_FOR_CLAUDE_CODE.md`):
- `sgraph_search_elements` - Find symbols by pattern
- `sgraph_get_element_dependencies` - THE KEY TOOL with `result_level` abstraction
- `sgraph_get_element_structure` - Explore hierarchy without reading source
- `sgraph_analyze_change_impact` - Impact analysis before code changes

## Development Notes

- Uses `uv` as package manager
- Ruff for linting (line length 100, Python 3.13 target)
- A model for this project exists at `/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip` - use it via the MCP tools for faster architectural exploration

## AI Experience Tracking

When experiencing notably good or bad moments with MCP tools, log them to `AI-EXPERIENCES.md` with format: MCP-server, tool name, rating (+/++/+++/-/--/---), short story.
