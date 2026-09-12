#!/usr/bin/env python3
"""
Integration tests for the deferred --auto-load model, exercised through the real
registered MCP tools.

The contract this PR adds: a model configured at startup is not parsed until a
tool actually needs it, and from the caller's side nothing changes - tools still
work with no explicit sgraph_load_model call.
"""

import json
import os
import sys

import pytest
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import src.profiles.base as base  # noqa: E402
from src.core.model_manager import ModelManager  # noqa: E402
from src.profiles.claude_code import ClaudeCodeProfile  # noqa: E402

MODEL_PATH = "tests/sgraph-and-mcp.xml.zip"


@pytest.fixture
def deferred_server(monkeypatch):
    """A claude-code profile server with a model configured but not yet parsed."""
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")

    manager = ModelManager()
    monkeypatch.setattr(base, "_model_manager", manager)

    mcp = FastMCP("test")
    ClaudeCodeProfile().register_tools(mcp)
    manager.set_deferred_model(MODEL_PATH)
    return mcp, manager


def _payload(result):
    """Unwrap a FastMCP tool result into the dict the tool returned."""
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


@pytest.mark.asyncio
async def test_registering_the_startup_model_parses_nothing(deferred_server):
    _, manager = deferred_server

    assert manager._models == {}
    assert manager.default_model_id is None


@pytest.mark.asyncio
async def test_a_search_loads_the_deferred_model_without_an_explicit_load(deferred_server):
    mcp, manager = deferred_server

    result = await mcp.call_tool(
        "sgraph_search_elements", {"input": {"query": "*ModelManager*"}}
    )

    assert "error" not in _payload(result)
    assert manager.default_model_id is not None


@pytest.mark.asyncio
async def test_load_model_returns_the_deferred_model_and_reports_it_as_fresh(deferred_server):
    mcp, manager = deferred_server

    result = _payload(await mcp.call_tool("sgraph_load_model", {"input": {"path": MODEL_PATH}}))

    assert result["model_id"] == manager.default_model_id
    assert result["cached"] is False

    again = _payload(await mcp.call_tool("sgraph_load_model", {"input": {"path": MODEL_PATH}}))
    assert again["model_id"] == result["model_id"]
    assert again["cached"] is True


@pytest.mark.asyncio
async def test_a_broken_startup_model_tells_the_caller_why(monkeypatch, tmp_path):
    manager = ModelManager()
    monkeypatch.setattr(base, "_model_manager", manager)
    mcp = FastMCP("test")
    ClaudeCodeProfile().register_tools(mcp)
    missing = str(tmp_path / "absent.xml.zip")
    manager.set_deferred_model(missing)

    result = _payload(
        await mcp.call_tool("sgraph_search_elements", {"input": {"query": "*"}})
    )

    # The old background loader swallowed this into "No model loaded", hiding a
    # misconfigured path behind a message telling the agent to do what it just did.
    assert missing in result["error"]
