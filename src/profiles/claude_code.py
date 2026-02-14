"""
Claude Code profile - optimized for AI-assisted software development.

Tools:
- sgraph_load_model: Load graph file (shared)
- sgraph_search_elements: Find elements by name within scope
- sgraph_get_element_dependencies: Dependencies with result_level abstraction
- sgraph_get_element_structure: Hierarchy navigation (children)
- sgraph_analyze_change_impact: Multi-level impact analysis

Design principles:
- Paths as first-class citizens (unambiguous element identification)
- Abstraction as query parameter (result_level: function/file/module)
- Progressive disclosure (5 tools vs 13+)
- Plain text TOON output (line-oriented, no JSON wrappers)
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
# TOON Output Helpers
# =============================================================================


def _format_structure(elem, current_depth: int, max_depth: int, lines: list[str]) -> None:
    """Append indented TOON lines for element hierarchy."""
    indent = "  " * current_depth
    etype = elem.getType() or "element"
    lines.append(f"{indent}{elem.getPath()} [{etype}] {elem.name}")

    if current_depth < max_depth and elem.children:
        for child in elem.children:
            _format_structure(child, current_depth + 1, max_depth, lines)


def _collect_deps(element, base_path: str, direction: str, result_level, include_descendants: bool) -> list[str]:
    """Collect dependency lines for an element, optionally including descendants.

    For outgoing: "-> /target (type)" or "RelativeChild -> /target (type)"
    For incoming: "/source (type) ->" or "/source (type) -> RelativeChild"
    Relative paths (no leading /) identify which descendant has the dependency.
    """
    lines = []
    seen = set()

    def aggregate(path: str) -> str:
        if result_level is None:
            return path
        parts = path.split("/")
        return "/".join(parts[:result_level + 1]) if len(parts) > result_level else path

    def collect_for_element(elem):
        # Compute relative path from base element (empty string for self)
        elem_path = elem.getPath()
        if elem_path == base_path:
            relative = ""
        else:
            relative = elem_path[len(base_path) + 1:]  # strip base_path + "/"

        if direction in ("outgoing", "both"):
            for assoc in elem.outgoing:
                target = aggregate(assoc.toElement.getPath())
                dep_type = getattr(assoc, 'type', '')
                key = ("out", relative, target, dep_type)
                if key not in seen:
                    seen.add(key)
                    type_suffix = f" ({dep_type})" if dep_type else ""
                    if relative:
                        lines.append(f"{relative} -> {target}{type_suffix}")
                    else:
                        lines.append(f"-> {target}{type_suffix}")

        if direction in ("incoming", "both"):
            for assoc in elem.incoming:
                source = aggregate(assoc.fromElement.getPath())
                dep_type = getattr(assoc, 'type', '')
                key = ("in", source, relative, dep_type)
                if key not in seen:
                    seen.add(key)
                    type_suffix = f" ({dep_type})" if dep_type else ""
                    if relative:
                        lines.append(f"{source}{type_suffix} -> {relative}")
                    else:
                        lines.append(f"{source}{type_suffix} ->")

        if include_descendants:
            for child in elem.children:
                collect_for_element(child)

    collect_for_element(element)
    return lines


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


class ResolveLocalPathInput(BaseModel):
    """Input for sgraph_resolve_local_path - map sgraph paths to local filesystem."""
    sgraph_path: str = Field(description="Sgraph element path (e.g., /TalenomSoftware/Online/repo/file.cs)")


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
    description = "Optimized for Claude Code - plain text TOON output"

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

            Returns plain text, one element per line: /path/to/element [type] name
            First line shows match count: "N/M matches" (shown/total).
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
                lines = [f"{len(limited)}/{len(elements)} matches"]
                for e in limited:
                    etype = e.getType() or "element"
                    lines.append(f"{e.getPath()} [{etype}] {e.name}")

                return "\n".join(lines)
            except Exception as e:
                return f"error: Search failed: {e}"

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

            Returns plain text. Outgoing: "-> /target (type)". Incoming: "/source (type) ->".
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
                sections = []

                if input.direction in ("outgoing", "both"):
                    out_lines = _collect_deps(
                        element, input.element_path, "outgoing",
                        input.result_level, input.include_descendants,
                    )
                    sections.append(f"outgoing ({len(out_lines)}):")
                    sections.extend(out_lines) if out_lines else sections.append("  (none)")

                if input.direction in ("incoming", "both"):
                    in_lines = _collect_deps(
                        element, input.element_path, "incoming",
                        input.result_level, input.include_descendants,
                    )
                    sections.append(f"incoming ({len(in_lines)}):")
                    sections.extend(in_lines) if in_lines else sections.append("  (none)")

                return "\n".join(sections)
            except Exception as e:
                return f"error: Dependency query failed: {e}"

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

            Returns plain text with indented hierarchy.
            Each line: /path/to/element [type] name
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
                lines = []
                _format_structure(element, 0, input.max_depth, lines)
                return "\n".join(lines)
            except Exception as e:
                return f"error: Structure query failed: {e}"

        @mcp.tool()
        async def sgraph_analyze_change_impact(input: AnalyzeChangeImpactInput):
            """BEFORE modifying any public interface, call this to see what breaks.

            Returns ALL abstraction levels at once (no need for multiple calls):
            - detailed: Every function/method that uses this element
            - by_file: Which files would need changes
            - by_module: Which modules/repos are affected

            When to use:
            - Before changing function signature -> see all call sites
            - Before renaming class -> see all importers
            - Before deleting code -> verify nothing depends on it
            - Planning large refactoring -> understand blast radius

            Returns plain text with sections for each aggregation level.
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
                detailed = []
                files = set()
                modules = set()

                for assoc in element.incoming:
                    source_path = assoc.fromElement.getPath()
                    detailed.append(source_path)

                    parts = source_path.split("/")
                    if len(parts) >= 3:
                        files.add("/".join(parts[:3]))
                    if len(parts) >= 2:
                        modules.add("/".join(parts[:2]))

                sections = [
                    f"impact: {len(detailed)} callers, {len(files)} files, {len(modules)} modules",
                    "",
                    f"detailed ({len(detailed)}):",
                ]
                sections.extend(detailed) if detailed else sections.append("  (none)")
                sections.append("")
                sections.append(f"by_file ({len(files)}):")
                sections.extend(sorted(files)) if files else sections.append("  (none)")
                sections.append("")
                sections.append(f"by_module ({len(modules)}):")
                sections.extend(sorted(modules)) if modules else sections.append("  (none)")

                return "\n".join(sections)
            except Exception as e:
                return f"error: Impact analysis failed: {e}"

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
