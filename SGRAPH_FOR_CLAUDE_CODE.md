# SGraph MCP Server for Claude Code

This guide explains how to use the sgraph-mcp-server tools effectively in Claude Code sessions.

## Why SGraph?

Claude Code discovers code structure through iterative `grep` and `Read` calls. This is:
- **Token expensive**: Reading files to understand imports fills context
- **Lossy**: grep returns comments, strings, and unrelated matches
- **Slow**: Multiple round-trips to trace call chains

SGraph provides **pre-computed dependency graphs** that answer architectural questions in a single call.

## Quick Start

```bash
# Start the server with Claude Code profile (5 optimized tools)
uv run python -m src.server --profile claude-code

# With auto-loaded model and default scope
uv run python -m src.server --profile claude-code \
  --auto-load /path/to/model.xml.zip \
  --default-scope /Project/repo
```

Add to Claude Code's MCP config (`.mcp.json` in project root):
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

## The 5 Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `sgraph_load_model` | Load graph file | Once per session |
| `sgraph_search_elements` | Find symbols by name | When you know name but not path |
| `sgraph_get_element_dependencies` | Query dependencies | Before modifying code |
| `sgraph_get_element_structure` | Explore hierarchy | Instead of Read to see contents |
| `sgraph_analyze_change_impact` | Full impact analysis | Before any public interface change |

## Output Format

All tools return **plain text using TOON (Token-Optimized Object Notation) line notation** - not JSON. This minimizes token usage and is easier for LLMs to parse.

Each tool has its own TOON line format:
- **search_elements**: `/path [type] name`
- **get_element_dependencies**: `-> /target (type)` or `/source (type) ->`
- **get_element_structure**: indented `/path [type] name`
- **analyze_change_impact**: sections with paths grouped by aggregation level

---

## Tool Reference

### sgraph_load_model

Load a graph model file. Required before using other tools (unless `--auto-load` is configured).

```python
sgraph_load_model(path="/path/to/model.xml.zip")
# Returns: {"model_id": "abc123...", "cached": true, "default_scope": "..."}
```

If `--auto-load` is configured, the model loads at startup and `model_id` can be omitted from all other calls.

---

### sgraph_search_elements

Find code elements by name pattern. **Use instead of grep for symbol lookup.**

```python
# Find all Manager classes
sgraph_search_elements(query="*Manager*", element_types=["class"])

# Find files matching a pattern in a specific subtree
sgraph_search_elements(
    query="*Service*",
    scope_path="/Project/src/auth",
    element_types=["file"]
)
```

**Output:**
```
3/12 matches
/project/src/core/model_manager.py/ModelManager [class] ModelManager
/project/src/auth/session_manager.py/SessionManager [class] SessionManager
/project/src/cache/cache_manager.py/CacheManager [class] CacheManager
```

First line: `shown/total matches`. Each subsequent line: `/path [type] name`.

**Parameters:**
- `query`: Wildcards (`*Service*`), regex (`.*Service.*`), or substring (`Service`)
- `scope_path`: Limit search to subtree (uses server default scope if not set)
- `element_types`: Filter by `["class", "function", "method", "file", "directory"]`
- `max_results`: Limit results (default 50)

---

### sgraph_get_element_dependencies

**THE KEY TOOL** - Query dependencies with abstraction level control.

```python
# What calls this function? (raw detail)
sgraph_get_element_dependencies(
    element_path="/project/src/auth/manager.py/AuthManager/validate",
    direction="incoming"
)

# What repos does this repo depend on?
sgraph_get_element_dependencies(
    element_path="/project/src/myrepo",
    direction="outgoing",
    result_level=2,
    include_descendants=True
)
```

**Output (element's own dependencies):**
```
outgoing (2):
-> /project/src/db/user_repo.py/UserRepo (call)
-> /project/src/crypto/service.py/hash (call)
incoming (3):
/project/src/api/endpoints.py/get_user (call) ->
/project/src/api/endpoints.py/delete_user (call) ->
/project/src/middleware/auth.py/check (call) ->
```

**Output (with `include_descendants=True`):**
```
outgoing (4):
-> /external/requests (import)
AuthManager/validate -> /project/src/db/user_repo.py/UserRepo (call)
AuthManager/validate -> /project/src/crypto/service.py/hash (call)
AuthManager/refresh -> /project/src/cache/store.py/TokenStore (call)
```

Relative paths (no leading `/`) identify which descendant owns the dependency. Absolute paths (leading `/`) are the targets.

**Parameters:**
| Parameter | Description |
|-----------|-------------|
| `direction` | `"incoming"`, `"outgoing"`, or `"both"` |
| `result_level` | Aggregate: `None`=raw, `4`=file, `3`=directory, `2`=repository |
| `include_descendants` | `false` (default): only this element. `true`: include children recursively |
| `include_external` | Include third-party dependencies (default `true`) |

**result_level** controls abstraction - same data, different granularity:
| Level | Meaning | Example: 41 raw deps becomes... |
|-------|---------|--------------------------------|
| `None` | Raw (as captured) | 41 individual function calls |
| `4` | File level | 5 unique files |
| `3` | Directory level | 2 unique directories |
| `2` | Repository level | 2 unique repos |

---

### sgraph_get_element_structure

Explore what's inside a file, class, or directory **without reading source code**.

```python
# What's in the services directory?
sgraph_get_element_structure(
    element_path="/project/src/services",
    max_depth=2
)
```

**Output:**
```
/project/src/services [dir] services
  /project/src/services/auth_service.py [file] auth_service.py
    /project/src/services/auth_service.py/AuthService [class] AuthService
    /project/src/services/auth_service.py/validate_token [function] validate_token
  /project/src/services/user_service.py [file] user_service.py
    /project/src/services/user_service.py/UserService [class] UserService
```

Indentation shows hierarchy. Each line: `/path [type] name`.

**Parameters:**
- `max_depth`: `1` = direct children only, `2` = two levels (usually sufficient), `3+` = deeper

**When to use:**
- Before deciding which file to Read (cheaper exploration)
- Understanding class structure without reading source
- Directory exploration without ls/find

---

### sgraph_analyze_change_impact

**"Measure twice, cut once"** - Full impact analysis before changes.

```python
sgraph_analyze_change_impact(
    element_path="/project/src/auth/manager.py/AuthManager/validate"
)
```

**Output:**
```
impact: 3 callers, 2 files, 1 modules

detailed (3):
/project/src/api/endpoints.py/UserEndpoint/get_profile
/project/src/api/endpoints.py/AdminEndpoint/delete_user
/project/src/middleware/auth.py/require_auth

by_file (2):
/project/src/api
/project/src/middleware

by_module (1):
/project/src
```

First line is a summary. Then three sections show the same callers aggregated at different levels.

**When to use:**
- Before changing function signature -> see all call sites
- Before renaming class -> see all importers
- Before deleting code -> verify nothing depends on it
- Planning refactoring -> understand blast radius

---

## Workflow Examples

### Example 1: Modifying a Function Signature

**Task**: Change `validate(token)` to `validate(token, strict=False)`

```
1. LOCATE the function:
   sgraph_search_elements(query="validate", scope_path="/project/src/auth")
   -> /project/src/auth/manager.py/AuthManager/validate [method] validate

2. CHECK IMPACT before changing:
   sgraph_analyze_change_impact(element_path="...validate")
   -> impact: 3 callers, 2 files, 1 modules

3. PLAN changes:
   - Modify validate() signature
   - Update all 3 call sites
   - Add tests for new parameter

4. EXECUTE: Edit all files in one coordinated change

5. VERIFY: Run tests
```

### Example 2: Understanding Cross-Repo Dependencies

**Task**: What external packages does this repo depend on?

```
1. QUERY at repository level with descendants:
   sgraph_get_element_dependencies(
       element_path="/Project/repo",
       direction="outgoing",
       result_level=2,
       include_descendants=True
   )
   -> outgoing (6):
      -> /Project/External
      -> /Project/OtherRepo
      Repo/src/api.csproj -> /Project/Utilities
      Repo/src/service.csproj -> /Project/SharedLib
      ...

2. DRILL DOWN into specific dependency:
   sgraph_get_element_dependencies(
       element_path="/Project/repo/src/service.csproj",
       direction="outgoing"
   )
```

### Example 3: Safe Refactoring

**Task**: Move `UserService` to a different module

```
1. ANALYZE full impact:
   sgraph_analyze_change_impact(element_path=".../UserService")
   -> impact: 15 callers, 8 files, 3 modules

2. GET detailed callers:
   sgraph_get_element_dependencies(element_path=".../UserService", direction="incoming")
   -> incoming (15):
      /project/src/api/user_endpoint.py/get_user (call) ->
      /project/src/api/admin.py/list_users (call) ->
      ...

3. PLAN: Update all 15 import statements after move

4. EXECUTE: Move file + update all imports

5. VERIFY: Tests pass, no broken imports
```

---

## Best Practices

### Do This

1. **Load model once** at session start, reuse `model_id`
2. **Use search before dependencies** - find the path first
3. **Check impact before changes** - avoid "fix one, break three" cycles
4. **Use structure instead of Read** for exploration - much cheaper
5. **Start with high result_level**, drill down if needed
6. **Use `include_descendants=True`** to see which child element causes each dependency
7. **Widen `scope_path`** when searching for symbols in other repos (e.g., NuGet sources)

### Don't Do This

1. Don't use grep for finding symbols (lossy, matches comments/strings)
2. Don't Read files to understand structure (token expensive)
3. Don't modify code without checking incoming dependencies
4. Don't make multiple calls when one tool returns all levels

---

## Path Format

All paths in SGraph are hierarchical:

```
/Organization/Category/repository/src/directory/file.py/ClassName/method_name
```

Examples:
- Repository: `/TalenomSoftware/Online/talenom.online.invoicepayment5.api`
- File: `/TalenomSoftware/Online/repo/src/auth/manager.py`
- Class: `/TalenomSoftware/Online/repo/src/auth/manager.py/AuthManager`
- External: `/TalenomSoftware/External/Python/requests`

Paths are **unambiguous** - no confusion about which `validate` you mean.

## Scope and Default Scope

The `--default-scope` CLI parameter limits searches to a subtree by default:

```bash
uv run python -m src.server --profile claude-code \
  --default-scope /TalenomSoftware/Online/my-repo
```

To search outside the default scope, pass `scope_path` explicitly:
```python
sgraph_search_elements(query="*CompanyIdentity*", scope_path="/TalenomSoftware")
```
