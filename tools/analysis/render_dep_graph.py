#!/usr/bin/env python3
"""
Render a dependency graph (DOT + SVG) for the sgraph-mcp-server subtree
using the local SGraphHelper on the latest.xml.zip model.

This mirrors the MCP tool logic but runs locally for easy artifact generation.
"""

import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, Any, Set, Tuple

from src.sgraph_helper import SGraphHelper


def sanitize_id(path: str) -> str:
    """Create a stable, DOT-safe node id from a path."""
    # Use quoted id; also append a short hash to avoid collisions on same basename
    base = path or "<root>"
    short_hash = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f'"{base}::{short_hash}"'


def label_for(path: str) -> str:
    """Human-friendly label for a node."""
    if not path:
        return "<root>"
    name = path.rstrip("/").split("/")[-1] or "/"
    return name


def build_dot(deps: Dict[str, Any]) -> str:
    nodes: Set[str] = set()
    edges: Set[Tuple[str, str]] = set()

    # Only show internal dependencies to keep the graph readable
    for dep in deps.get("internal_dependencies", []):
        src = dep.get("from", "")
        dst = dep.get("to", "")
        if not src or not dst:
            continue
        nodes.add(src)
        nodes.add(dst)
        edges.add((src, dst))

    lines = []
    lines.append("digraph G {")
    lines.append("  rankdir=LR;")
    lines.append("  graph [fontname=Helvetica, fontsize=10, splines=true, overlap=false];")
    lines.append("  node  [fontname=Helvetica, fontsize=9, shape=box, style=rounded];")
    lines.append("  edge  [fontname=Helvetica, fontsize=8, color=gray40, arrowsize=0.7];")

    # Nodes
    for path in sorted(nodes):
        node_id = sanitize_id(path)
        label = label_for(path)
        tooltip = path or "<root>"
        lines.append(f"  {node_id} [label=\"{label}\", tooltip=\"{tooltip}\"]; ")

    # Edges
    for src, dst in sorted(edges):
        src_id = sanitize_id(src)
        dst_id = sanitize_id(dst)
        lines.append(f"  {src_id} -> {dst_id};")

    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    model_path = os.environ.get(
        "SGRAPH_MODEL",
        "/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip",
    )
    subtree = "/sgraph-and-mcp/sgraph-mcp-server"
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    dot_path = output_dir / "sgraph-mcp-server-deps.dot"
    svg_path = output_dir / "sgraph-mcp-server-deps.svg"

    helper = SGraphHelper()
    # Load model and compute dependencies locally
    model_id = helper._models.get("__tmp__")
    if not model_id:
        # Load the model (cached in helper)
        # Note: load_sgraph is async; run blocking through asyncio.run
        import asyncio

        asyncio.run(helper.load_sgraph(model_path))

    # Grab the (single) model instance from cache
    # Since helper returns a random id, just get the last one
    model = list(helper._models.values())[-1]
    deps = helper.get_subtree_dependencies(
        model,
        root_path=subtree,
        include_external=False,
        max_depth=3,
    )

    dot = build_dot(deps)
    dot_path.write_text(dot, encoding="utf-8")

    # Render to SVG with dot
    ret = os.system(f'dot -Tsvg "{dot_path}" -o "{svg_path}"')
    if ret != 0:
        print("dot rendering failed", file=sys.stderr)
        sys.exit(2)

    print(f"DOT: {dot_path}")
    print(f"SVG: {svg_path}")


if __name__ == "__main__":
    main()


