#!/usr/bin/env python3
"""
Structural guard: every claude-code tool must resolve the default model lazily.

Each tool repeats the same two lines to find a model, so the deferred load is
wired in by hand nine times over. A missed `await` is silent - the coroutine
object is truthy, so the `if not mid` guard passes and the caller gets
"Model '<coroutine object ...>' not found" instead of their data.

This reads the tool list out of the source rather than hard-coding it, so a tool
added later without the wiring fails here instead of at runtime.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

PROFILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'profiles', 'claude_code.py'
)


def _model_using_tools():
    """Every async sgraph_* tool in the profile that resolves a model itself."""
    with open(PROFILE, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name.startswith("sgraph_")
        and node.name != "sgraph_load_model"
        and "model_manager" in ast.dump(node)
    ]


def _awaits_ensure_default_model(func: ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(func):
        if not isinstance(node, ast.Await):
            continue
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            if call.func.attr == "ensure_default_model":
                return True
    return False


def _reports_no_model_error(func: ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "no_model_error"
        for node in ast.walk(func)
    )


def test_the_profile_still_has_tools_that_resolve_a_model():
    """Guard the guard: an empty population would make everything below vacuous."""
    assert len(_model_using_tools()) >= 9


def test_every_tool_awaits_the_deferred_model():
    missing = [f.name for f in _model_using_tools() if not _awaits_ensure_default_model(f)]

    assert missing == [], f"tools not awaiting ensure_default_model(): {missing}"


def test_every_tool_reports_why_no_model_is_available():
    missing = [f.name for f in _model_using_tools() if not _reports_no_model_error(f)]

    assert missing == [], f"tools not using no_model_error(): {missing}"
