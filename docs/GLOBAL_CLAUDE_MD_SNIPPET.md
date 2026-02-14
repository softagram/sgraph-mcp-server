# SGraph Integration for Claude Code

Add this section to your `~/.claude/CLAUDE.md` to enable sgraph-aware development.

---

## SGraph Code Intelligence

You have access to **sgraph** - pre-computed dependency graphs that answer architectural questions instantly instead of grep/read cycles.

### STOP Before Searching for Dependencies

**When about to grep/Glob for callers, usages, or imports → use sgraph instead.**

| You're about to... | Use this instead |
|-------------------|------------------|
| grep/Glob for "what calls X" | `sgraph_get_element_dependencies(direction="incoming")` |
| grep/Glob for "what does X use" | `sgraph_get_element_dependencies(direction="outgoing")` |
| Manually trace impact of a change | `sgraph_analyze_change_impact()` |
| Read files to understand structure | `sgraph_get_element_structure()` |

**Why:** grep misses indirect callers and takes multiple rounds. sgraph finds everything in one call.

### Convention

| Item | Location |
|------|----------|
| **Model path** | `/tmp/analysis-outputs/<project-name>/latest.xml.zip` |
| **Analyzer** | `~/analyze.sh <source-dir> --output-dir /tmp/analysis-outputs/<project-name>` |
| **MCP server** | `http://localhost:8008/sse` (claude-code profile) |
| **File watcher** | `sgraph-watcher` (auto-reanalyzes on code changes) |

### Quick Check: Is a Model Available?

```bash
ls -la /tmp/analysis-outputs/*/latest.xml.zip
```

### File Watcher (Automatic Re-analysis)

The `sgraph-watcher` daemon monitors your projects and automatically re-analyzes when code changes (with 3-minute debounce).

```bash
# Check watcher status and model freshness
sgraph-watcher status

# Add a project to auto-watch
sgraph-watcher add /path/to/project

# Force immediate analysis
sgraph-watcher analyze /path/to/project
```

Status indicators:
- ✅ **fresh** - Model is up-to-date with code
- ⚠️ **stale** - Code changed since last analysis (watcher will re-analyze)
- ❌ **no model** - Never analyzed (run `sgraph-watcher analyze`)

### Workflow

**1. Check model freshness:**
```bash
sgraph-watcher status  # Shows ✅ fresh / ⚠️ stale / ❌ no model
```

**2. If no model or stale, analyze (or let watcher handle it):**
```bash
# Option A: Let watcher auto-analyze (if project is watched)
sgraph-watcher add /path/to/project  # Add once, auto-updates

# Option B: Force immediate analysis
sgraph-watcher analyze /path/to/project
```

**3. Load and query via MCP:**
```
sgraph_load_model(path="/tmp/analysis-outputs/<project-name>/latest.xml.zip")
→ model_id

sgraph_get_element_dependencies(model_id, element_path, direction="incoming")
→ What calls this function?

sgraph_analyze_change_impact(model_id, element_path)
→ What breaks if I change this?
```

### When to Use SGraph vs Native Tools

| Task | Without SGraph | With SGraph |
|------|----------------|-------------|
| Find all callers of a function | grep (noisy, misses indirect) | `sgraph_get_element_dependencies(direction="incoming")` |
| Impact of changing an API | Manual search, easy to miss | `sgraph_analyze_change_impact()` |
| Understand module structure | Read multiple files | `sgraph_get_element_structure()` |
| Find symbol location | grep/Glob | `sgraph_search_elements()` |

### MCP Server

The sgraph-mcp-server should be running:

```bash
sgraph-mcp  # Starts with claude-code profile (default)
```

### Tools Reference (claude-code profile)

| Tool | Purpose |
|------|---------|
| `sgraph_load_model` | Load model file, get model_id |
| `sgraph_search_elements` | Find symbols by pattern (replaces grep for code search) |
| `sgraph_get_element_dependencies` | **KEY TOOL** - query dependencies with `result_level` abstraction and `include_descendants` |
| `sgraph_get_element_structure` | Explore hierarchy without reading source |
| `sgraph_analyze_change_impact` | Check what breaks before modifying code |

### Project Name Convention

Use the directory name as the project name:

| Source Directory | Output Directory | Model Path |
|-----------------|------------------|------------|
| `~/code/my-app` | `/tmp/analysis-outputs/my-app` | `/tmp/analysis-outputs/my-app/latest.xml.zip` |
| `~/code/backend` | `/tmp/analysis-outputs/backend` | `/tmp/analysis-outputs/backend/latest.xml.zip` |

### Example Session

```
User: "What would break if I change the validate() function in auth.py?"

Claude:
1. Check model freshness:
   sgraph-watcher status
   → /Users/me/code/my-project: ✅ fresh

2. Load model (model is fresh, proceed):
   sgraph_load_model(path="/tmp/analysis-outputs/my-project/latest.xml.zip")
   → model_id: "abc123"

3. Find the function:
   sgraph_search_elements(model_id="abc123", query=".*validate.*")
   → /my-project/src/auth.py/validate [function]

4. Check impact:
   sgraph_analyze_change_impact(model_id="abc123", element_path="/my-project/src/auth.py/validate")
   → 5 callers in 3 files
```

If `sgraph-watcher status` shows ⚠️ stale, run `sgraph-watcher analyze /path/to/project` first.
