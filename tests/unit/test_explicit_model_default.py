#!/usr/bin/env python3
"""
A model loaded with sgraph_load_model must be usable without repeating its ID.

Every query tool takes model_id as optional and falls back to the default model.
Only the --auto-load startup model used to become the default, so in a session
without one the natural sequence - load the model, then query it - failed with
"No model loaded. Call sgraph_load_model first." right after the load succeeded.

The fix makes the first explicitly loaded model the default. That alone would
have broken loading a second model, because sgraph_load_model returned the
default whatever path it was asked for; it now does so only for the default's
own path.
"""

import json
import os
import sys

import pytest
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import src.profiles.base as base
from src.core.model_manager import ModelManager

MODEL_TEMPLATE = """<model version="2.1">
  <elements>
    <e n="{name}" t="dir">
      <e n="a.py" t="file"/>
    </e>
  </elements>
</model>
"""


@pytest.fixture
def model_a(tmp_path):
    path = tmp_path / "a.xml"
    path.write_text(MODEL_TEMPLATE.format(name="project_a"))
    return str(path)


@pytest.fixture
def model_b(tmp_path):
    path = tmp_path / "b.xml"
    path.write_text(MODEL_TEMPLATE.format(name="project_b"))
    return str(path)


class TestExplicitLoadBecomesDefault:

    def setup_method(self):
        self.manager = ModelManager()

    @pytest.mark.asyncio
    async def test_the_first_loaded_model_becomes_the_default(self, model_a):
        model_id = await self.manager.load_model(model_a)

        assert await self.manager.ensure_default_model() == model_id

    @pytest.mark.asyncio
    async def test_a_second_load_does_not_replace_the_default(self, model_a, model_b):
        first = await self.manager.load_model(model_a)
        second = await self.manager.load_model(model_b)

        assert second != first
        assert self.manager.default_model_id == first

    @pytest.mark.asyncio
    async def test_an_explicit_load_does_not_displace_a_configured_startup_model(
        self, model_a, model_b
    ):
        self.manager.set_deferred_model(model_a)

        await self.manager.load_model(model_b)
        startup_id = await self.manager.ensure_default_model()

        assert self.manager._model_paths[startup_id] == os.path.abspath(model_a)


async def _call_load_model(mcp: FastMCP, path: str) -> dict:
    result = await mcp.call_tool("sgraph_load_model", {"input": {"path": path}})
    # FastMCP 1.9 returns the content list; later 1.x versions return
    # (content, structured_output).
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


class TestLoadModelTool:

    def setup_method(self):
        base._model_manager = None
        self.mcp = FastMCP("test")
        base.register_load_model(self.mcp)

    def teardown_method(self):
        base._model_manager = None

    @pytest.mark.asyncio
    async def test_loading_a_second_model_returns_that_model(self, model_a, model_b):
        first = await _call_load_model(self.mcp, model_a)
        second = await _call_load_model(self.mcp, model_b)

        assert second["model_id"] != first["model_id"]
        model = base.get_model_manager().get_model(second["model_id"])
        assert model.rootNode.children[0].name == "project_b"

    @pytest.mark.asyncio
    async def test_reloading_the_default_path_reuses_the_loaded_model(self, model_a):
        first = await _call_load_model(self.mcp, model_a)
        again = await _call_load_model(self.mcp, model_a)

        assert again["model_id"] == first["model_id"]
        assert again["cached"] is True
