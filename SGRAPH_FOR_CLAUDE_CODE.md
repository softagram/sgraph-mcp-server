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

## The 8 Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `sgraph_load_model` | Load graph file | Once per session |
| `sgraph_search_elements` | Find symbols by name | When you know name but not path |
| `sgraph_get_element_dependencies` | Query dependencies | Before modifying code |
| `sgraph_get_element_structure` | Explore hierarchy | Instead of Read to see contents |
| `sgraph_analyze_change_impact` | Impact analysis with warnings | Before any public interface change |
| `sgraph_audit` | Architectural health checks | Tech debt reviews, onboarding |
| `sgraph_security_audit` | Security overview (6 dimensions) | Security posture, audit prep, risk prioritization |
| `sgraph_resolve_local_path` | Map sgraph path to filesystem | When you need to read source code |

## Output Format

All tools return **JSON** — structured data that LLMs parse reliably regardless of nesting depth.

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
```json
{
  "shown": 3, "total": 12,
  "elements": [
    {"path": "/project/src/core/model_manager.py/ModelManager", "type": "class", "name": "ModelManager"},
    {"path": "/project/src/auth/session_manager.py/SessionManager", "type": "class", "name": "SessionManager"},
    {"path": "/project/src/cache/cache_manager.py/CacheManager", "type": "class", "name": "CacheManager"}
  ]
}
```

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
```json
{
  "outgoing": [
    {"direction": "outgoing", "target": "/project/src/db/user_repo.py/UserRepo", "type": "call"},
    {"direction": "outgoing", "target": "/project/src/crypto/service.py/hash", "type": "call"}
  ],
  "incoming": [
    {"direction": "incoming", "source": "/project/src/api/endpoints.py/get_user", "type": "call"},
    {"direction": "incoming", "source": "/project/src/api/endpoints.py/delete_user", "type": "call"},
    {"direction": "incoming", "source": "/project/src/middleware/auth.py/check", "type": "call"}
  ]
}
```

**Output (with `include_descendants=True`):**
```json
{
  "outgoing": [
    {"direction": "outgoing", "target": "/external/requests", "type": "import"},
    {"direction": "outgoing", "target": "/project/src/db/user_repo.py/UserRepo", "type": "call", "from_descendant": "AuthManager/validate"},
    {"direction": "outgoing", "target": "/project/src/crypto/service.py/hash", "type": "call", "from_descendant": "AuthManager/validate"},
    {"direction": "outgoing", "target": "/project/src/cache/store.py/TokenStore", "type": "call", "from_descendant": "AuthManager/refresh"}
  ]
}
```

`from_descendant` / `to_descendant` fields identify which child element owns the dependency.

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
```json
{
  "path": "/project/src/services", "type": "dir", "name": "services",
  "children": [
    {"path": "/project/src/services/auth_service.py", "type": "file", "name": "auth_service.py",
     "children": [
       {"path": "/project/src/services/auth_service.py/AuthService", "type": "class", "name": "AuthService"},
       {"path": "/project/src/services/auth_service.py/validate_token", "type": "function", "name": "validate_token"}
     ]},
    {"path": "/project/src/services/user_service.py", "type": "file", "name": "user_service.py",
     "children": [
       {"path": "/project/src/services/user_service.py/UserService", "type": "class", "name": "UserService"}
     ]}
  ]
}
```

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
```json
{
  "summary": {"callers": 3, "files": 2, "modules": 2},
  "warnings": [
    {"type": "dependency_cycle", "message": "Bidirectional deps with 1 module(s)...", "modules": ["/project/src/middleware"]},
    {"type": "hub_element", "message": "42 outgoing deps — changes here cascade widely"}
  ],
  "detailed": [
    "/project/src/api/endpoints.py/UserEndpoint/get_profile",
    "/project/src/api/endpoints.py/AdminEndpoint/delete_user",
    "/project/src/middleware/auth.py/require_auth"
  ],
  "by_file": ["/project/src/api/endpoints.py", "/project/src/middleware/auth.py"],
  "by_module": ["/project/src/api", "/project/src/middleware"]
}
```

Warnings appear only when detected:
- **dependency_cycle**: bidirectional module deps — changes may cascade in both directions
- **hub_element**: >30 outgoing deps — high-coupling element

**When to use:**
- Before changing function signature -> see all call sites
- Before renaming class -> see all importers
- Before deleting code -> verify nothing depends on it
- Planning refactoring -> understand blast radius

---

### sgraph_audit

**Architectural health checks** — for occasional tech debt reviews, not daily use.

```python
sgraph_audit(
    scope_path="/project/src",
    checks=["cycles", "hubs"],
    aggregation_level=3
)
```

**Output:**
```json
{
  "total_modules": 12, "total_dependencies": 45,
  "cycles": [
    {"module1": "/project/src/core", "module2": "/project/src/api", "forward": 12, "backward": 5},
    {"module1": "/project/src/auth", "module2": "/project/src/middleware", "forward": 3, "backward": 2}
  ],
  "most_dependent": [
    {"path": "/project/src/api", "outgoing": 8},
    {"path": "/project/src/core", "outgoing": 6}
  ],
  "most_depended_upon": [
    {"path": "/project/src/models", "incoming": 9},
    {"path": "/project/src/utils", "incoming": 7}
  ]
}
```

**aggregation_level** controls granularity:
| Level | Meaning | Example |
|-------|---------|---------|
| `2` | Component level | `/project/component` (good for monorepos) |
| `3` | Module level | `/project/component/module` (default) |
| `4+` | Sub-module level | Deeper nesting |

**When to use:**
- Tech debt reviews -> find circular dependencies
- New developer onboarding -> understand module coupling
- Architecture audits -> identify hub modules
- **Not** during regular feature development (use `analyze_change_impact` instead)

---

### sgraph_security_audit

**Security posture overview** across 6 dimensions in a single call. Works on any sgraph model — from a single repo to an organization with hundreds of repositories.

```python
# Full security audit
sgraph_security_audit(top_n=10)

# Scoped to a specific repository
sgraph_security_audit(scope_path="/Organization/Platform/my-service", top_n=5)
```

**Output:**
```json
{
  "summary": {
    "total_repositories": 42,
    "total_files": 85000,
    "dimensions_found": ["secrets", "vulnerabilities", "outdated", "risk", "backstage", "bus_factor"]
  },
  "secrets": {
    "total": 47,
    "by_type": {"Hex High Entropy String": 30, "Base64 High Entropy String": 12, "unknown": 5},
    "top_repos": [
      {"repo": "/Organization/Platform/config-service", "count": 15},
      {"repo": "/Organization/Platform/legacy-api", "count": 8}
    ]
  },
  "vulnerabilities": {
    "total": 25,
    "by_severity": {"critical": 3, "high": 8, "moderate": 10, "low": 4},
    "top_repos": []
  },
  "outdated": {
    "total_eol": 5,
    "total_approaching_eol": 3,
    "items": [
      {"path": "/Organization/External/DotNet/TFM/net5.0", "platform": "DotNet", "outdated": "fully", "end_of_life": "2022-05-10"}
    ],
    "frameworks_deprecated": [
      {"path": "/Organization/External/DotNet/TFM/net5.0/net5.0 is deprecated", "description": "net5.0 reached end of life"}
    ]
  },
  "risk": {
    "high_risk_repos": [
      {"path": "/Organization/Platform/legacy-api", "risk_density": 450.2, "softagram_index": 23, "architecture_modularity": 31, "loc": 45000}
    ],
    "avg_softagram_index": 62.5,
    "distribution": {"0-25": 2, "25-50": 8, "50-75": 20, "75-100": 12}
  },
  "backstage": {
    "services_found": 15,
    "by_lifecycle": {"production": 10, "deprecated": 3, "experimental": 2},
    "exposed_to_public": ["public-api", "web-frontend"],
    "owners": {"team-platform": 8, "team-core": 5, "team-data": 2}
  },
  "bus_factor": {
    "single_author_files": [
      {"path": "/Organization/Platform/billing/src/invoice_engine.py", "loc": 3200, "author_count_365": 1}
    ],
    "low_author_repos": [
      {"path": "/Organization/Platform/legacy-api", "total_loc": 45000, "avg_author_count": 1.1}
    ]
  }
}
```

**The 6 dimensions:**

| Dimension | What it finds | Key insight |
|-----------|--------------|-------------|
| **secrets** | API keys, tokens, national IDs committed to code | "Where are leaked credentials?" |
| **vulnerabilities** | Known CVEs in dependencies, by severity | "How many critical vulns exist?" |
| **outdated** | End-of-life frameworks, approaching-EOL packages | "What needs upgrading before it becomes a risk?" |
| **risk** | Code quality metrics (Softagram Index 0-100) | "Which repos have the worst code quality?" |
| **backstage** | Service catalog: owners, lifecycle, public exposure | "Who owns what? What's exposed to the internet?" |
| **bus_factor** | Single-author critical files, low-author repos | "What breaks if someone leaves the team?" |

**Notes:**
- Non-code files (XML, JSON, YAML, etc.) are excluded from bus factor analysis
- Dimensions with no data return empty/zero values (not errors)
- `top_n` limits all ranked lists (default 10)
- Softagram Index: 0 = disaster, 100 = excellent (combination of risk density and architecture modularity)

**When to use:**
- Organizational security audit — "What's the security posture across all our repos?"
- Risk prioritization — "Which repos need attention first?"
- Compliance preparation — "Show me all EOL frameworks"
- Team review — "Which critical code has only one author?"

---

## Workflow Examples

### Example 1: Security Audit of an Organization

**Task**: Assess security posture across all repositories

```
1. LOAD the organization model:
   sgraph_load_model(path="/path/to/org-model.xml.zip")
   -> model_id: "abc123"

2. RUN full security audit:
   sgraph_security_audit(model_id="abc123", top_n=10)
   -> summary: 3 critical vulns, 47 secrets, 5 EOL frameworks, 2 bus factor risks

3. PRIORITIZE by severity:
   - Fix 3 critical vulnerabilities immediately
   - Rotate 47 leaked secrets
   - Plan migration for 5 EOL frameworks
   - Address bus factor in billing/invoice_engine.py (3200 LOC, 1 author)

4. DRILL DOWN into specific repo:
   sgraph_security_audit(model_id="abc123", scope_path="/Organization/Platform/legacy-api")
   -> Detailed view of just that repo's security issues

5. CHECK what depends on the vulnerable library:
   sgraph_get_element_dependencies(
       element_path="/Organization/External/NPM/lodash of version 4.17.0",
       direction="incoming", result_level=2
   )
   -> Shows which repos import the vulnerable version
```

### Example 2: Modifying a Function Signature

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
- Repository: `/Organization/Platform/billing-service`
- File: `/Organization/Online/repo/src/auth/manager.py`
- Class: `/Organization/Online/repo/src/auth/manager.py/AuthManager`
- External: `/Organization/External/Python/requests`

Paths are **unambiguous** - no confusion about which `validate` you mean.

## Scope and Default Scope

The `--default-scope` CLI parameter limits searches to a subtree by default:

```bash
uv run python -m src.server --profile claude-code \
  --default-scope /Organization/Online/my-repo
```

To search outside the default scope, pass `scope_path` explicitly:
```python
sgraph_search_elements(query="*UserService*", scope_path="/Organization")
```
