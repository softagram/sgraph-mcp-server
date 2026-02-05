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
```

Add to Claude Code's MCP config:
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

---

## Tool Reference

### sgraph_load_model

Load a graph model file. Required before using other tools.

```python
sgraph_load_model(path="/path/to/model.xml.zip")
# Returns: {"model_id": "abc123..."}
```

**Note**: Save the `model_id` - you'll need it for all subsequent calls.

---

### sgraph_search_elements

Find code elements by name pattern. **Use instead of grep for symbol lookup.**

```python
# Find all Manager classes
sgraph_search_elements(
    model_id="...",
    query=".*Manager",
    element_types=["class"]
)

# Find functions starting with "validate" in auth module
sgraph_search_elements(
    model_id="...",
    query="^validate.*",
    scope_path="/project/src/auth",
    element_types=["function"]
)
```

**Output (TOON format)**:
```
/project/src/core/model_manager.py/ModelManager [class] ModelManager
/project/src/auth/session_manager.py/SessionManager [class] SessionManager
```

**When to use**:
- You know a class/function name but not its location
- Finding all implementations matching a pattern
- Locating a symbol before querying its dependencies

---

### sgraph_get_element_dependencies

**THE KEY TOOL** - Query dependencies with abstraction level control.

```python
# What functions call this function? (before changing signature)
sgraph_get_element_dependencies(
    model_id="...",
    element_path="/project/src/auth/manager.py/AuthManager/validate",
    direction="incoming",
    result_level=None  # Raw function-level detail
)

# What FILES depend on this file? (planning file move)
sgraph_get_element_dependencies(
    model_id="...",
    element_path="/project/src/auth/manager.py",
    direction="incoming",
    result_level=4  # Aggregated to file level
)

# What does this class use? (understanding implementation)
sgraph_get_element_dependencies(
    model_id="...",
    element_path="/project/src/api/UserService",
    direction="outgoing"
)
```

**Direction explained**:
- `"incoming"`: What **uses** this element (callers, importers) → impact analysis
- `"outgoing"`: What this element **uses** (callees, imports) → understanding context
- `"both"`: Both in one call

**result_level explained** (THE KEY FEATURE):
| Level | Meaning | Example |
|-------|---------|---------|
| `None` | Raw (as captured) | 41 individual function calls |
| `4` | File level | 5 unique files |
| `3` | Directory level | 2 unique directories |
| `2` | Repository level | 2 unique repos |

Same underlying data, different abstraction. One parameter changes the view.

**Output (TOON format)**:
```
/project/src/api/endpoints.py/get_user -> /project/src/auth/manager.py/validate
/project/src/middleware/auth.py/check -> /project/src/auth/manager.py/validate
```

---

### sgraph_get_element_structure

Explore what's inside a file, class, or directory **without reading source code**.

```python
# What classes/functions are in this file?
sgraph_get_element_structure(
    model_id="...",
    element_path="/project/src/core/model_manager.py",
    max_depth=2
)

# What's in the services directory?
sgraph_get_element_structure(
    model_id="...",
    element_path="/project/src/services",
    max_depth=2
)
```

**Output**:
```json
{
  "path": "/project/src/core/model_manager.py",
  "type": "file",
  "name": "model_manager.py",
  "children": [
    {
      "path": ".../ModelManager",
      "type": "class",
      "name": "ModelManager",
      "children": [
        {"path": ".../load_model", "type": "method", "name": "load_model"},
        {"path": ".../get_model", "type": "method", "name": "get_model"}
      ]
    }
  ]
}
```

**When to use**:
- Before deciding which file to Read (cheaper exploration)
- Understanding class structure without source
- Directory exploration without ls/find

---

### sgraph_analyze_change_impact

**"Measure twice, cut once"** - Full impact analysis before changes.

```python
sgraph_analyze_change_impact(
    model_id="...",
    element_path="/project/src/auth/manager.py/AuthManager/validate"
)
```

**Output**:
```json
{
  "element": "/project/src/auth/manager.py/AuthManager/validate",
  "element_type": "method",
  "incoming_by_level": {
    "detailed": [
      "/project/src/api/endpoints.py/UserEndpoint/get_profile",
      "/project/src/api/endpoints.py/AdminEndpoint/delete_user",
      "/project/src/middleware/auth.py/require_auth"
    ],
    "file": ["/project/src/api", "/project/src/middleware"],
    "module": ["/project/src"]
  },
  "summary": {
    "incoming_count": 3,
    "files_affected": 2,
    "modules_affected": 1
  }
}
```

**When to use**:
- Before changing function signature → see all call sites
- Before renaming class → see all importers
- Before deleting code → verify nothing depends on it
- Planning refactoring → understand blast radius

---

## Workflow Examples

### Example 1: Modifying a Function Signature

**Task**: Change `validate(token)` to `validate(token, strict=False)`

```
1. LOCATE the function:
   sgraph_search_elements(query="validate", scope_path="/project/src/auth")
   → /project/src/auth/manager.py/AuthManager/validate

2. CHECK IMPACT before changing:
   sgraph_analyze_change_impact(element_path="...validate")
   → 3 callers in 2 files

3. PLAN changes:
   - Modify validate() signature
   - Update all 3 call sites
   - Add tests for new parameter

4. EXECUTE: Edit all files in one coordinated change

5. VERIFY: Run tests
```

### Example 2: Understanding a New Codebase

**Task**: Understand how authentication works

```
1. FIND auth-related classes:
   sgraph_search_elements(query=".*[Aa]uth.*", element_types=["class"])
   → AuthManager, AuthMiddleware, AuthConfig

2. EXPLORE structure of main class:
   sgraph_get_element_structure(element_path=".../AuthManager", max_depth=2)
   → Shows: validate(), refresh_token(), revoke() methods

3. CHECK what AuthManager depends on:
   sgraph_get_element_dependencies(element_path=".../AuthManager", direction="outgoing")
   → Uses: TokenStore, UserRepository, CryptoService

4. NOW read specific files with full context understanding
```

### Example 3: Safe Refactoring

**Task**: Move `UserService` to a different module

```
1. ANALYZE full impact:
   sgraph_analyze_change_impact(element_path=".../UserService")
   → incoming_count: 15, files_affected: 8, modules_affected: 3

2. GET detailed callers:
   sgraph_get_element_dependencies(element_path=".../UserService", direction="incoming")
   → List of all 15 import sites

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

### Don't Do This

1. ❌ Use grep for finding symbols (lossy, matches comments/strings)
2. ❌ Read files to understand structure (token expensive)
3. ❌ Modify code without checking incoming dependencies
4. ❌ Make multiple calls when one tool returns all levels

---

## Comparison: Without vs With SGraph

### Without SGraph (Native Claude Code)

```
Claude: *wants to modify validate() signature*
Claude: grep -r "validate" src/
→ 247 matches (comments, strings, unrelated functions)
Claude: *reads 10 files trying to find actual callers*
Claude: *misses one caller in obscure file*
Claude: *makes change*
Tests: FAIL - missed caller breaks
Claude: *reads error, finds missed file, fixes*
Tests: FAIL - another missed caller
... (repeat 5×, context saturated)
```

### With SGraph

```
Claude: *wants to modify validate() signature*
Claude: sgraph_analyze_change_impact(element_path=".../validate")
→ Exactly 3 callers in 2 files, with full paths
Claude: *modifies validate() and all 3 call sites*
Tests: PASS
```

**Result**: Proactive impact analysis replaces reactive error fixing.

---

## Path Format

All paths in SGraph are hierarchical:

```
/project-name/repository/src/directory/file.py/ClassName/method_name
```

Examples:
- File: `/myproject/backend/src/auth/manager.py`
- Class: `/myproject/backend/src/auth/manager.py/AuthManager`
- Method: `/myproject/backend/src/auth/manager.py/AuthManager/validate`
- External: `/myproject/External/Python/requests`

Paths are **unambiguous** - no confusion about which `validate` you mean.

---

## TOON Output Format

Tools return **TOON (Token-Optimized Object Notation)** - 50-60% fewer tokens than JSON.

```
# JSON (~45 tokens)
{"source":"src/api/endpoints.py/get_user","target":"src/auth/manager.py/validate","type":"call"}

# TOON (~15 tokens)
src/api/endpoints.py/get_user -> src/auth/manager.py/validate (call)
```

Line-oriented format is easier to scan and cheaper to process.
