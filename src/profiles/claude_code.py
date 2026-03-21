"""
Claude Code profile - optimized for AI-assisted software development.

Tools:
- sgraph_load_model: Load graph file (shared)
- sgraph_search_elements: Find elements by name within scope
- sgraph_get_element_dependencies: Dependencies with result_level abstraction
- sgraph_get_element_structure: Hierarchy navigation (children)
- sgraph_analyze_change_impact: Multi-level impact analysis (with cycle/hub warnings)
- sgraph_audit: Architectural health checks (cycles, hubs) — for occasional reviews
- sgraph_security_audit: Security overview (secrets, vulns, EOL, risk, backstage, bus factor)

Design principles:
- Paths as first-class citizens (unambiguous element identification)
- Abstraction as query parameter (result_level: function/file/module)
- Progressive disclosure (7 tools vs 13+)
- JSON output for reliable parsing by LLMs
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.profiles import register_profile
from src.profiles.base import get_model_manager, register_load_model
from src.services.search_service import SearchService
from src.services.dependency_service import DependencyService
from src.core.element_converter import ElementConverter
from src.services.security_service import SecurityService


# =============================================================================
# Output Helpers
# =============================================================================


def _format_structure(elem, current_depth: int, max_depth: int) -> dict:
    """Build a dict for element hierarchy."""
    result = {
        "path": elem.getPath(),
        "type": elem.getType() or "element",
        "name": elem.name,
    }
    if current_depth < max_depth and elem.children:
        result["children"] = [
            _format_structure(child, current_depth + 1, max_depth)
            for child in elem.children
        ]
    return result


def _collect_deps(element, base_path: str, direction: str, result_level, include_descendants: bool) -> list[dict]:
    """Collect dependency dicts for an element, optionally including descendants."""
    deps = []
    seen = set()

    def aggregate(path: str) -> str:
        if result_level is None:
            return path
        parts = path.split("/")
        return "/".join(parts[:result_level + 1]) if len(parts) > result_level else path

    def collect_for_element(elem):
        elem_path = elem.getPath()
        relative = "" if elem_path == base_path else elem_path[len(base_path) + 1:]

        if direction in ("outgoing", "both"):
            for assoc in elem.outgoing:
                target = aggregate(assoc.toElement.getPath())
                dep_type = getattr(assoc, 'type', '')
                key = ("out", relative, target, dep_type)
                if key not in seen:
                    seen.add(key)
                    entry = {"direction": "outgoing", "target": target}
                    if dep_type:
                        entry["type"] = dep_type
                    if relative:
                        entry["from_descendant"] = relative
                    deps.append(entry)

        if direction in ("incoming", "both"):
            for assoc in elem.incoming:
                source = aggregate(assoc.fromElement.getPath())
                dep_type = getattr(assoc, 'type', '')
                key = ("in", source, relative, dep_type)
                if key not in seen:
                    seen.add(key)
                    entry = {"direction": "incoming", "source": source}
                    if dep_type:
                        entry["type"] = dep_type
                    if relative:
                        entry["to_descendant"] = relative
                    deps.append(entry)

        if include_descendants:
            for child in elem.children:
                collect_for_element(child)

    collect_for_element(element)
    return deps


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


def _get_file_path(path: str) -> str:
    """Extract the file path from an element path (up to and including the .ext segment)."""
    parts = path.split("/")
    for i, part in enumerate(parts):
        if "." in part:
            return "/".join(parts[:i + 1])
    return path


# =============================================================================
# Input Schemas
# =============================================================================


class SearchElementsInput(BaseModel):
    """Input for sgraph_search_elements."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
    query: str = Field(description="Name pattern (supports wildcards like '*Service*' or regex like '.*Service.*')")
    scope_path: Optional[str] = Field(
        default=None,
        description="Limit search to subtree. Uses server's default scope if configured and not specified."
    )
    element_types: Optional[list[str]] = Field(
        default=None,
        description="Filter by type: ['class', 'function', 'method', 'file', 'directory']"
    )
    max_results: int = Field(default=50, description="Maximum results to return")


class GetElementDependenciesInput(BaseModel):
    """Input for sgraph_get_element_dependencies."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
    element_path: str = Field(description="Full hierarchical path to element")
    direction: Literal["incoming", "outgoing", "both"] = Field(
        default="both",
        description="incoming=what uses this, outgoing=what this uses"
    )
    result_level: Optional[int] = Field(
        default=None,
        description=(
            "Aggregate results to hierarchy depth. "
            "None=raw (as captured), 4=file, 3=directory, 2=repository"
        )
    )
    include_descendants: bool = Field(
        default=False,
        description="Include dependencies of child elements. Relative paths (no leading /) show which descendant."
    )
    include_external: bool = Field(
        default=True,
        description="Include external/third-party dependencies"
    )


class GetElementStructureInput(BaseModel):
    """Input for sgraph_get_element_structure."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
    element_path: str = Field(description="Starting point path")
    max_depth: int = Field(default=2, description="How deep to traverse children")


class AnalyzeChangeImpactInput(BaseModel):
    """Input for sgraph_analyze_change_impact."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
    element_path: str = Field(description="Element being modified")


class AuditInput(BaseModel):
    """Input for sgraph_audit — architectural health checks."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
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


class ResolveLocalPathInput(BaseModel):
    """Input for sgraph_resolve_local_path - map sgraph paths to local filesystem."""
    sgraph_path: str = Field(description="Sgraph element path (e.g., /TalenomSoftware/Online/repo/file.cs)")


class SecurityAuditInput(BaseModel):
    """Input for sgraph_security_audit."""
    model_id: Optional[str] = Field(default=None, description="Model ID (omit to use auto-loaded default)")
    scope_path: Optional[str] = Field(
        default=None,
        description="Limit audit to subtree (e.g., '/Project/Group/repo')"
    )
    top_n: int = Field(
        default=10,
        description="Maximum items in ranked lists (default 10)"
    )


# =============================================================================
# Path Resolution (sgraph -> local filesystem)
# =============================================================================

import json
import os
from pathlib import Path

_path_resolver_config = None


def _load_path_config():
    """Load path mapping configuration."""
    global _path_resolver_config
    if _path_resolver_config is not None:
        return _path_resolver_config

    config = {"mappings": [], "fallback_roots": ["/mnt/c/code/"], "repo_overrides": {}}

    # Search for config file
    search_paths = [
        Path(__file__).parent.parent.parent / "sgraph-mapping.json",
        Path.cwd() / "sgraph-mapping.json",
        Path.home() / ".config" / "sgraph-mapping.json",
    ]

    for p in search_paths:
        if p.exists():
            with open(p, 'r') as f:
                config = json.load(f)
            break

    _path_resolver_config = config
    return config


def _resolve_sgraph_path(sgraph_path: str) -> dict:
    """Resolve sgraph path to local filesystem path."""
    config = _load_path_config()
    parts = sgraph_path.strip('/').split('/')

    result = {
        "sgraph_path": sgraph_path,
        "repo_name": parts[2] if len(parts) > 2 else None,
        "local_path": None,
        "exists": False,
        "resolved_via": "not_found"
    }

    if len(parts) < 3:
        return result

    repo_name = parts[2]
    repo_name = config.get("repo_name_overrides", {}).get(repo_name, repo_name)
    result["repo_name"] = repo_name

    # Try mappings
    for mapping in config.get("mappings", []):
        prefix = mapping.get("sgraph_prefix", "/")
        if sgraph_path.startswith(prefix):
            local_root = mapping.get("local_root", "")
            strip_levels = mapping.get("strip_levels", 2)

            remaining_parts = parts[strip_levels + 1:] if len(parts) > strip_levels + 1 else []
            local_path = os.path.join(local_root, repo_name, *remaining_parts)

            if os.path.exists(local_path):
                result["local_path"] = local_path
                result["exists"] = True
                result["resolved_via"] = "mapping"
                return result

            if result["local_path"] is None:
                result["local_path"] = local_path

    # Try fallback roots
    remaining_parts = parts[3:] if len(parts) > 3 else []
    for root in config.get("fallback_roots", []):
        root = os.path.expanduser(root)
        local_path = os.path.join(root, repo_name, *remaining_parts)
        if os.path.exists(local_path):
            result["local_path"] = local_path
            result["exists"] = True
            result["resolved_via"] = "fallback"
            return result

    return result


# =============================================================================
# Profile Implementation
# =============================================================================


@register_profile("claude-code")
class ClaudeCodeProfile:
    """Profile optimized for Claude Code IDE integration."""

    name = "claude-code"
    description = "Optimized for Claude Code - JSON output"

    def register_tools(self, mcp: FastMCP) -> None:
        """Register Claude Code-optimized tools with the MCP server."""
        register_load_model(mcp)
        model_manager = get_model_manager()

        @mcp.tool()
        async def sgraph_search_elements(input: SearchElementsInput):
            """Find code elements by name pattern. Use instead of grep for precise symbol lookup.

            When to use:
            - You know a class/function name but not its file location
            - You want to find all implementations of a pattern (e.g., "*Service*", "*Handler")
            - You need to locate a symbol before querying its dependencies

            Parameters:
            - query: Wildcards ("*Service*") or regex (".*Service.*") or substring ("Service")
            - scope_path: Limit to subtree - faster, fewer results. Auto-set if server has default scope.
            - element_types: Filter by ["class", "function", "method", "file", "dir"]
            - model_id: Omit to use auto-loaded model

            Returns JSON with match count and element list.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            scope = input.scope_path or model_manager.default_scope

            try:
                elements = SearchService.search_elements_by_name(
                    model,
                    input.query,
                    element_type=input.element_types[0] if input.element_types else None,
                    scope_path=scope,
                )

                limited = elements[:input.max_results]
                return {
                    "shown": len(limited),
                    "total": len(elements),
                    "elements": [
                        {"path": e.getPath(), "type": e.getType() or "element", "name": e.name}
                        for e in limited
                    ],
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

            result_level (controls abstraction):
            - None: Raw dependencies (function->function) - for precise call sites
            - 4: File level - "which files depend on this?"
            - 3: Directory level - "which directories depend on this?"
            - 2: Repository level - "which repos depend on this?"

            include_descendants:
            - false (default): Only this element's own dependencies
            - true: Also include children's dependencies. Relative paths (no leading /)
              show which descendant: "MyClass/Save -> /target (call)"

            Returns JSON with outgoing/incoming dependency lists.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            try:
                result = {}

                if input.direction in ("outgoing", "both"):
                    out_deps = _collect_deps(
                        element, input.element_path, "outgoing",
                        input.result_level, input.include_descendants,
                    )
                    result["outgoing"] = out_deps

                if input.direction in ("incoming", "both"):
                    in_deps = _collect_deps(
                        element, input.element_path, "incoming",
                        input.result_level, input.include_descendants,
                    )
                    result["incoming"] = in_deps

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
            - 1: Direct children only (file->classes, dir->files)
            - 2: Two levels (file->classes->methods) - usually sufficient
            - 3+: Deeper nesting (rarely needed)

            Returns JSON hierarchy with path, type, name, and children.
            Much cheaper than Read - use this first to decide what to read.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            try:
                return _format_structure(element, 0, input.max_depth)
            except Exception as e:
                return {"error": f"Structure query failed: {e}"}

        @mcp.tool()
        async def sgraph_analyze_change_impact(input: AnalyzeChangeImpactInput):
            """BEFORE modifying any public interface, call this to see what breaks.

            Returns ALL abstraction levels at once (no need for multiple calls):
            - detailed: Every function/method that uses this element
            - by_file: Which files would need changes
            - by_module: Which modules/repos are affected

            Automatic warnings (when detected):
            - dependency_cycle: bidirectional module deps — blast radius exceeds listed callers
            - hub_element: >30 outgoing deps — changes cascade widely

            When to use:
            - Before changing function signature -> see all call sites
            - Before renaming class -> see all importers
            - Before deleting code -> verify nothing depends on it
            - Planning large refactoring -> understand blast radius

            Returns JSON with summary, warnings, and callers at multiple aggregation levels.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            element = model.findElementFromPath(input.element_path)
            if element is None:
                return {"error": f"Element not found: {input.element_path}"}

            try:
                # Collect all elements in subtree (element + children, recursive)
                subtree = []
                stack = [element]
                while stack:
                    e = stack.pop()
                    subtree.append(e)
                    stack.extend(e.children)
                subtree_paths = {e.getPath() for e in subtree}

                # Collect all incoming (what uses this element or its children)
                detailed = []
                files = set()
                modules = set()
                incoming_dirs = set()

                for e in subtree:
                    for assoc in e.incoming:
                        source_path = assoc.fromElement.getPath()
                        if source_path in subtree_paths:
                            continue
                        if "/External/" in source_path:
                            continue
                        detailed.append(source_path)
                        files.add(_get_file_path(source_path))
                        modules.add(_get_parent_dir(source_path))
                        incoming_dirs.add(_get_parent_dir(source_path))

                # Collect outgoing deps for cycle/hub warnings
                outgoing_dirs = set()
                outgoing_count_non_external = 0

                for e in subtree:
                    for assoc in e.outgoing:
                        target_path = assoc.toElement.getPath()
                        if "/External/" in target_path:
                            continue
                        if target_path in subtree_paths:
                            continue
                        outgoing_count_non_external += 1
                        outgoing_dirs.add(_get_parent_dir(target_path))

                # Detect cycles: directories in both incoming and outgoing
                element_dir = _get_parent_dir(input.element_path)
                incoming_dirs.discard(element_dir)
                outgoing_dirs.discard(element_dir)
                cycle_dirs = incoming_dirs & outgoing_dirs

                # Build result
                result = {
                    "summary": {
                        "callers": len(detailed),
                        "files": len(files),
                        "modules": len(modules),
                    },
                    "warnings": [],
                    "detailed": detailed,
                    "by_file": sorted(files),
                    "by_module": sorted(modules),
                }

                if cycle_dirs:
                    result["warnings"].append({
                        "type": "dependency_cycle",
                        "message": f"Bidirectional deps with {len(cycle_dirs)} module(s) — blast radius likely exceeds listed callers",
                        "modules": sorted(cycle_dirs),
                    })

                if outgoing_count_non_external > 30:
                    result["warnings"].append({
                        "type": "hub_element",
                        "message": f"{outgoing_count_non_external} outgoing deps — changes here cascade widely",
                    })

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

            Returns JSON with cycles, hub modules, and summary metrics.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            try:
                analysis = DependencyService.get_high_level_dependencies(
                    model,
                    scope_path=input.scope_path,
                    aggregation_level=input.aggregation_level,
                    include_external=False,
                    include_metrics=True,
                )

                if "error" in analysis:
                    return {"error": analysis["error"]}

                result = {
                    "total_modules": analysis.get("total_modules", 0),
                    "total_dependencies": analysis.get("total_dependencies", 0),
                }

                if "cycles" in input.checks:
                    raw_cycles = analysis.get("metrics", {}).get(
                        "circular_dependencies", []
                    )
                    result["cycles"] = [
                        {
                            "module1": c["module1"],
                            "module2": c["module2"],
                            "forward": c["count_1_to_2"],
                            "backward": c["count_2_to_1"],
                        }
                        for c in raw_cycles
                    ]

                if "hubs" in input.checks:
                    modules = analysis.get("modules", [])
                    hub_threshold = 5
                    result["most_dependent"] = sorted(
                        [
                            {"path": m["path"], "outgoing": m["outgoing_count"]}
                            for m in modules if m["outgoing_count"] >= hub_threshold
                        ],
                        key=lambda x: x["outgoing"],
                        reverse=True,
                    )[:10]
                    result["most_depended_upon"] = sorted(
                        [
                            {"path": m["path"], "incoming": m["incoming_count"]}
                            for m in modules if m["incoming_count"] >= hub_threshold
                        ],
                        key=lambda x: x["incoming"],
                        reverse=True,
                    )[:10]

                return result

            except Exception as e:
                return {"error": f"Audit failed: {e}"}

        @mcp.tool()
        async def sgraph_resolve_local_path(input: ResolveLocalPathInput):
            """Map sgraph path to local filesystem path. Use to find source code for NuGet packages.

            When to use:
            - You found a class/method in sgraph and need to read its source code
            - You want to understand what a NuGet package method does internally
            - You need to navigate from dependency analysis to actual code

            The mapping is configured in sgraph-mapping.json. Default maps:
            - /TalenomSoftware/<category>/<repo>/... -> /mnt/c/code/<repo>/...

            Returns:
            - sgraph_path: Original path
            - repo_name: Git repository name (3rd level in hierarchy)
            - local_path: Resolved filesystem path
            - exists: Whether the file/dir exists locally

            After resolving, use the Read tool to view the source code.
            """
            try:
                result = _resolve_sgraph_path(input.sgraph_path)
                return result
            except Exception as e:
                return {"error": f"Path resolution failed: {e}"}

        @mcp.tool()
        async def sgraph_security_audit(input: SecurityAuditInput):
            """Security overview across 6 dimensions: secrets, vulnerabilities,
            outdated/EOL, risk levels, backstage metadata, bus factor.

            Use for: organizational security posture, audit preparation, risk prioritization.

            Dimensions (only those with findings are included):
            - secrets: potential secrets committed to code (API keys, tokens, national IDs)
            - vulnerabilities: CVEs in dependencies, by severity
            - outdated: end-of-life frameworks and approaching-EOL packages
            - risk: code risk density and Softagram Index (0-100, higher=better)
            - backstage: service ownership, lifecycle, public exposure
            - bus_factor: single-author critical files, low-author repositories

            Returns JSON with summary + per-dimension breakdown.
            """
            mid = input.model_id or model_manager.default_model_id
            if not mid:
                return {"error": "No model loaded. Call sgraph_load_model first."}
            model = model_manager.get_model(mid)
            if model is None:
                return {"error": f"Model '{mid}' not found"}

            try:
                return SecurityService.audit(
                    model,
                    scope_path=input.scope_path,
                    top_n=input.top_n,
                )
            except Exception as e:
                return {"error": f"Security audit failed: {e}"}
