"""
Claude Code profile - optimized for AI-assisted software development.

Aligned with CC_synthesis.md specification. Provides consolidated tools
designed for Claude Code's context constraints:

Tools:
- sgraph_load_model: Load graph file (shared)
- sgraph_search_elements: Find elements by name within scope
- sgraph_get_element_dependencies: Dependencies with result_level abstraction
- sgraph_get_element_structure: Hierarchy navigation (children)
- sgraph_analyze_change_impact: Multi-level impact analysis (with cycle/hub warnings)
- sgraph_audit: Architectural health checks (cycles, hubs) — for occasional reviews

Design principles:
- Paths as first-class citizens (unambiguous element identification)
- Abstraction as query parameter (result_level: function/file/module)
- Progressive disclosure (6 tools vs 13+, 60% token reduction)
- TOON output format (line-oriented, 50-60% token savings)
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.profiles import register_profile
from src.profiles.base import get_model_manager, register_load_model
from src.services.search_service import SearchService
from src.services.dependency_service import DependencyService
from src.core.element_converter import ElementConverter


# =============================================================================
# TOON Output Format Utilities
# =============================================================================
# TOON (Token-Optimized Object Notation) reduces token consumption by 50-60%
# compared to verbose JSON. Line-oriented format for large datasets.
#
# Example:
#   JSON:  {"source":"src/A.ts","target":"src/B.ts","type":"import"}  (~45 tokens)
#   TOON:  src/A.ts -> src/B.ts (import)                              (~15 tokens)


def format_dependency_toon(from_path: str, to_path: str, dep_type: str = "") -> str:
    """Format a single dependency as TOON line."""
    if dep_type:
        return f"{from_path} -> {to_path} ({dep_type})"
    return f"{from_path} -> {to_path}"


def format_element_toon(path: str, element_type: str, name: str = "") -> str:
    """Format a single element as TOON line."""
    if name:
        return f"{path} [{element_type}] {name}"
    return f"{path} [{element_type}]"


def _get_parent_dir(path: str) -> str:
    """Get the parent directory of the file containing an element.

    For /project/src/module/file.py/ClassName → /project/src/module
    For /project/src/module/file.py → /project/src/module
    For /project/src/module (directory, no dot) → /project/src/module (itself)
    """
    parts = path.split("/")
    for i, part in enumerate(parts):
        if "." in part:  # Found file (has extension)
            return "/".join(parts[:i])
    # No file segment found — path is a directory, return it as-is
    return path


# =============================================================================
# Input Schemas (aligned with CC_synthesis.md)
# =============================================================================


class SearchElementsInput(BaseModel):
    """Input for sgraph_search_elements (CC_synthesis.md lines 275-291)."""
    model_id: str
    query: str = Field(description="Name pattern (supports wildcards like 'validate*')")
    scope_path: Optional[str] = Field(
        default=None,
        description="Limit search to subtree (e.g., '/project/src/auth')"
    )
    element_types: Optional[list[str]] = Field(
        default=None,
        description="Filter by type: ['class', 'function', 'method', 'file', 'directory']"
    )
    max_results: int = Field(default=50, description="Maximum results to return")


class GetElementDependenciesInput(BaseModel):
    """Input for sgraph_get_element_dependencies (CC_synthesis.md lines 171-218).

    The result_level parameter is THE KEY FEATURE - enables querying same
    underlying data at different abstraction levels.
    """
    model_id: str
    element_path: str = Field(description="Full hierarchical path to element")
    direction: Literal["incoming", "outgoing", "both"] = Field(
        default="both",
        description="incoming=what uses this, outgoing=what this uses"
    )
    result_level: Optional[int] = Field(
        default=None,
        description=(
            "Aggregate results to hierarchy depth. "
            "None=raw (as captured), 3=class, 2=file, 1=module/directory"
        )
    )
    max_depth: Optional[int] = Field(
        default=None,
        description="Transitive dependency traversal depth"
    )
    include_external: bool = Field(
        default=True,
        description="Include external/third-party dependencies"
    )


class GetElementStructureInput(BaseModel):
    """Input for sgraph_get_element_structure (CC_synthesis.md lines 222-244)."""
    model_id: str
    element_path: str = Field(description="Starting point path")
    max_depth: int = Field(default=2, description="How deep to traverse children")


class AnalyzeChangeImpactInput(BaseModel):
    """Input for sgraph_analyze_change_impact (CC_synthesis.md lines 248-271)."""
    model_id: str
    element_path: str = Field(description="Element being modified")


class AuditInput(BaseModel):
    """Input for sgraph_audit — architectural health checks."""
    model_id: str
    scope_path: Optional[str] = Field(
        default=None,
        description="Limit analysis to subtree (e.g., '/project/src')"
    )
    checks: list[Literal["cycles", "hubs"]] = Field(
        default=["cycles", "hubs"],
        description="Checks to run: 'cycles' (circular deps), 'hubs' (high-coupling modules)"
    )
    aggregation_level: int = Field(
        default=3,
        description="Directory depth for module grouping (3='/project/component/module')"
    )


# =============================================================================
# Profile Implementation
# =============================================================================


@register_profile("claude-code")
class ClaudeCodeProfile:
    """Profile optimized for Claude Code IDE integration.

    Implements CC_synthesis.md specification exactly:
    - sgraph_search_elements: Find elements by name within scope
    - sgraph_get_element_dependencies: THE KEY TOOL with result_level abstraction
    - sgraph_get_element_structure: Hierarchy navigation
    - sgraph_analyze_change_impact: Multi-level impact for change planning
    """

    name = "claude-code"
    description = "Optimized for Claude Code - CC_synthesis.md aligned"

    def register_tools(self, mcp: FastMCP) -> None:
        """Register Claude Code-optimized tools with the MCP server."""
        register_load_model(mcp)
        model_manager = get_model_manager()

        @mcp.tool()
        async def sgraph_search_elements(input: SearchElementsInput):
            """Find code elements by name pattern. Use instead of grep for precise symbol lookup.

            When to use:
            - You know a class/function name but not its file location
            - You want to find all implementations of a pattern (e.g., "*Service", "*Handler")
            - You need to locate a symbol before querying its dependencies

            Parameters:
            - query: Regex pattern (e.g., ".*Manager.*", "validate.*", "^test_")
            - scope_path: Limit to subtree (e.g., "/project/src/auth") - faster, fewer results
            - element_types: Filter by ["class", "function", "method", "file", "dir"]

            Returns TOON format: /path/to/element [type] name
            """
            model = model_manager.get_model(input.model_id)
            if model is None:
                return {"error": "Model not loaded"}

            try:
                # Use existing SearchService
                elements = SearchService.search_elements_by_name(
                    model,
                    input.query,
                    element_type=input.element_types[0] if input.element_types else None,
                    scope_path=input.scope_path,
                )

                # Limit and format as TOON
                limited = elements[:input.max_results]
                toon_lines = [
                    format_element_toon(e.getPath(), e.getType() or "element", e.name)
                    for e in limited
                ]

                return {
                    "results": toon_lines,
                    "count": len(limited),
                    "total_matches": len(elements),
                    "format": "TOON",
                }
            except Exception as e:
                return {"error": f"Search failed: {e}"}

        @mcp.tool()
        async def sgraph_get_element_dependencies(input: GetElementDependenciesInput):
            """Query what code depends on an element, or what it depends on. THE KEY TOOL.

            When to use:
            - Before modifying a function: check incoming (what calls this?)
            - Understanding a class: check outgoing (what does it use?)
            - Planning refactoring: check both directions

            Direction:
            - "incoming": What uses THIS element (callers, importers) - for impact analysis
            - "outgoing": What THIS element uses (callees, imports) - for understanding context
            - "both": Both directions in one call

            result_level (THE KEY FEATURE - controls abstraction):
            - None: Raw dependencies (function→function) - for precise call sites
            - 4: File level - "which files depend on this?"
            - 3: Directory level - "which directories depend on this?"
            - 2: Repository level - "which repos depend on this?"

            Example: SElement class with 41 raw deps → 2 unique at repo level

            Returns TOON format: /from/path -> /to/path (type)
            """
            model = model_manager.get_model(input.model_id)
            if model is None:
                return {"error": "Model not loaded"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            try:
                result = {
                    "element": input.element_path,
                    "direction": input.direction,
                    "result_level": input.result_level,
                    "format": "TOON",
                }

                def aggregate_to_level(path: str, level: Optional[int]) -> str:
                    """Aggregate path to specified hierarchy level."""
                    if level is None:
                        return path
                    parts = path.split("/")
                    # Level 1 = first 2 parts, level 2 = first 3 parts, etc.
                    return "/".join(parts[:level + 1]) if len(parts) > level else path

                def collect_dependencies(direction: str) -> list[str]:
                    """Collect and format dependencies for given direction."""
                    deps = []
                    seen = set()

                    if direction == "outgoing":
                        associations = element.outgoing
                        for assoc in associations:
                            target = assoc.toElement.getPath()
                            aggregated = aggregate_to_level(target, input.result_level)
                            if aggregated not in seen:
                                seen.add(aggregated)
                                dep_type = getattr(assoc, 'type', '')
                                deps.append(format_dependency_toon(
                                    input.element_path, aggregated, dep_type
                                ))
                    else:  # incoming
                        associations = element.incoming
                        for assoc in associations:
                            source = assoc.fromElement.getPath()
                            aggregated = aggregate_to_level(source, input.result_level)
                            if aggregated not in seen:
                                seen.add(aggregated)
                                dep_type = getattr(assoc, 'type', '')
                                deps.append(format_dependency_toon(
                                    aggregated, input.element_path, dep_type
                                ))

                    return deps

                if input.direction in ("outgoing", "both"):
                    result["outgoing"] = collect_dependencies("outgoing")
                    result["outgoing_count"] = len(result["outgoing"])

                if input.direction in ("incoming", "both"):
                    result["incoming"] = collect_dependencies("incoming")
                    result["incoming_count"] = len(result["incoming"])

                return result

            except Exception as e:
                return {"error": f"Dependency query failed: {e}"}

        @mcp.tool()
        async def sgraph_get_element_structure(input: GetElementStructureInput):
            """Explore what's inside a file, class, or directory WITHOUT reading source code.

            When to use:
            - See what classes/functions a file contains (instead of Read + scroll)
            - Explore a directory structure (instead of ls + recursive exploration)
            - Understand class methods before diving into implementation

            max_depth:
            - 1: Direct children only (file→classes, dir→files)
            - 2: Two levels (file→classes→methods) - usually sufficient
            - 3+: Deeper nesting (rarely needed)

            Returns nested JSON with path, type, name, children[].
            Much cheaper than Read - use this first to decide what to read.
            """
            model = model_manager.get_model(input.model_id)
            if model is None:
                return {"error": "Model not loaded"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            def build_structure(elem, current_depth: int, max_depth: int) -> dict:
                """Recursively build structure up to max_depth."""
                node = {
                    "path": elem.getPath(),
                    "type": elem.getType() or "element",
                    "name": elem.name,
                }

                if current_depth < max_depth and elem.children:
                    node["children"] = [
                        build_structure(child, current_depth + 1, max_depth)
                        for child in elem.children
                    ]

                return node

            try:
                structure = build_structure(element, 0, input.max_depth)
                return structure
            except Exception as e:
                return {"error": f"Structure query failed: {e}"}

        @mcp.tool()
        async def sgraph_analyze_change_impact(input: AnalyzeChangeImpactInput):
            """BEFORE modifying any public interface, call this to see what breaks.

            Returns ALL abstraction levels at once (no need for multiple calls):
            - detailed: Every function/method that uses this element
            - file: Which files would need changes
            - module: Which modules/repos are affected

            When to use:
            - Before changing function signature → see all call sites
            - Before renaming class → see all importers
            - Before deleting code → verify nothing depends on it
            - Planning large refactoring → understand blast radius

            Example output for SElement class:
              incoming_count: 41 (functions calling it)
              files_affected: 2 (files to modify)
              modules_affected: 2 (repos impacted)

            This is the "measure twice, cut once" tool.
            """
            model = model_manager.get_model(input.model_id)
            if model is None:
                return {"error": "Model not loaded"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            try:
                # Collect all elements in subtree (element + children, recursive)
                # This ensures file-level analysis captures deps on classes/functions inside
                subtree = []
                stack = [element]
                while stack:
                    e = stack.pop()
                    subtree.append(e)
                    stack.extend(e.children)

                # Collect all incoming (what uses this element or its children)
                detailed = []
                files = set()
                modules = set()
                incoming_dirs = set()
                element_subtree_paths = {e.getPath() for e in subtree}

                for e in subtree:
                    for assoc in e.incoming:
                        source_path = assoc.fromElement.getPath()
                        # Skip self-references and external deps
                        if source_path in element_subtree_paths:
                            continue
                        if "/External/" in source_path:
                            continue
                        detailed.append(source_path)

                        # Aggregate to file level (find first dotted segment)
                        src_parts = source_path.split("/")
                        file_path = source_path
                        for idx, seg in enumerate(src_parts):
                            if "." in seg:
                                file_path = "/".join(src_parts[:idx + 1])
                                break
                        files.add(file_path)

                        # Aggregate to module level (parent directory of file)
                        modules.add(_get_parent_dir(source_path))

                        # Track parent directories for cycle detection
                        incoming_dirs.add(_get_parent_dir(source_path))

                # Collect outgoing deps for cycle/hub warnings
                outgoing_dirs = set()
                outgoing_count_non_external = 0

                for e in subtree:
                    for assoc in e.outgoing:
                        target_path = assoc.toElement.getPath()
                        if "/External/" in target_path:
                            continue
                        if target_path in element_subtree_paths:
                            continue
                        outgoing_count_non_external += 1
                        outgoing_dirs.add(_get_parent_dir(target_path))

                # Detect cycles: directories that appear in both incoming and outgoing
                # (bidirectional dependency between this element's module and that module)
                element_dir = _get_parent_dir(input.element_path)
                incoming_dirs.discard(element_dir)
                outgoing_dirs.discard(element_dir)
                cycle_dirs = incoming_dirs & outgoing_dirs

                # Build warnings
                warnings = []
                if cycle_dirs:
                    warnings.append({
                        "type": "dependency_cycle",
                        "message": (
                            f"Bidirectional dependencies with {len(cycle_dirs)} "
                            f"module(s) — blast radius likely exceeds listed callers"
                        ),
                        "cycle_with": sorted(cycle_dirs),
                    })

                # Hub threshold: 30 outgoing non-external deps indicates a
                # high-coupling element where changes tend to cascade widely
                if outgoing_count_non_external > 30:
                    warnings.append({
                        "type": "hub_element",
                        "message": (
                            f"Hub element with {outgoing_count_non_external} outgoing "
                            f"dependencies — changes here cascade widely"
                        ),
                    })

                result = {
                    "element": input.element_path,
                    "element_type": element.getType() or "element",

                    "incoming_by_level": {
                        "detailed": detailed,
                        "file": sorted(files),
                        "module": sorted(modules),
                    },

                    "summary": {
                        "incoming_count": len(detailed),
                        "files_affected": len(files),
                        "modules_affected": len(modules),
                    },

                    "format": "TOON",
                }

                if warnings:
                    result["warnings"] = warnings

                return result

            except Exception as e:
                return {"error": f"Impact analysis failed: {e}"}

        @mcp.tool()
        async def sgraph_audit(input: AuditInput):
            """Run architectural health checks on the codebase. For occasional reviews, not daily use.

            Available checks:
            - "cycles": Find circular module dependencies (A depends on B, B depends on A)
            - "hubs": Find modules with unusually high coupling (many dependencies)

            aggregation_level controls module granularity:
            - 2: /project/component (coarse, good for monorepos)
            - 3: /project/component/module (default)
            - 4+: deeper nesting for fine-grained analysis

            Returns TOON format with cycles, hub modules, and summary metrics.
            """
            model = model_manager.get_model(input.model_id)
            if model is None:
                return {"error": "Model not loaded"}

            try:
                analysis = DependencyService.get_high_level_dependencies(
                    model,
                    scope_path=input.scope_path,
                    aggregation_level=input.aggregation_level,
                    include_external=False,
                    include_metrics=True,
                )

                if "error" in analysis:
                    return analysis

                result = {
                    "scope": analysis.get("scope_path"),
                    "aggregation_level": input.aggregation_level,
                    "format": "TOON",
                }

                if "cycles" in input.checks:
                    cycles = analysis.get("metrics", {}).get(
                        "circular_dependencies", []
                    )
                    result["cycles"] = {
                        "count": len(cycles),
                        "details": [
                            (
                                f"{c['module1']} <-> {c['module2']} "
                                f"({c['count_1_to_2']}→, {c['count_2_to_1']}←)"
                            )
                            for c in cycles
                        ],
                    }

                if "hubs" in input.checks:
                    modules = analysis.get("modules", [])
                    hub_threshold = 5
                    outgoing_hubs = [
                        m for m in modules
                        if m["outgoing_count"] >= hub_threshold
                    ]
                    incoming_hubs = [
                        m for m in modules
                        if m["incoming_count"] >= hub_threshold
                    ]

                    result["hubs"] = {
                        "most_dependent": [
                            f"{m['path']} ({m['outgoing_count']} outgoing)"
                            for m in sorted(
                                outgoing_hubs,
                                key=lambda x: x["outgoing_count"],
                                reverse=True,
                            )[:10]
                        ],
                        "most_depended_upon": [
                            f"{m['path']} ({m['incoming_count']} incoming)"
                            for m in sorted(
                                incoming_hubs,
                                key=lambda x: x["incoming_count"],
                                reverse=True,
                            )[:10]
                        ],
                    }

                result["summary"] = {
                    "total_modules": analysis.get("total_modules", 0),
                    "total_dependencies": analysis.get("total_dependencies", 0),
                }

                return result

            except Exception as e:
                return {"error": f"Audit failed: {e}"}
