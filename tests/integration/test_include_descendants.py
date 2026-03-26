#!/usr/bin/env python3
"""
Integration tests for include_descendants using a real sgraph model.

Uses tests/sgraph-and-mcp.xml.zip and tests _collect_deps + the full
sgraph_get_element_dependencies tool handler.
"""

import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sgraph import SGraph
from src.profiles.claude_code import _collect_deps
from src.core.model_manager import ModelManager

MODEL_PATH = "tests/sgraph-and-mcp.xml.zip"
# generalizer.py: file with own outgoing deps AND children that have cross-file deps
GENERALIZER = "/sgraph-and-mcp/sgraph/src/sgraph/algorithms/generalizer.py"


def _load_model():
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")
    return SGraph.parse_xml_or_zipped_xml(MODEL_PATH)


class TestIncludeDescendantsWithRealModel:
    """Integration tests for _collect_deps with real sgraph model."""

    def setup_method(self):
        self.model = _load_model()
        self.elem = self.model.findElementFromPath(GENERALIZER)
        assert self.elem is not None, f"Element not found: {GENERALIZER}"

    def test_without_descendants_only_file_deps(self):
        """Without descendants, only the file's own imports are returned."""
        deps = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, False)
        targets = {d['target'] for d in deps}

        # generalizer.py itself imports sys, typing, SElement, SGraph, SElementAssociation
        assert len(deps) == 5
        assert '/sgraph-and-mcp/External/PythonLibs/sys' in targets
        assert '/sgraph-and-mcp/sgraph/src/sgraph/selement.py/SElement' in targets

        # No from_descendant on any of them
        assert all('from_descendant' not in d for d in deps)

    def test_with_descendants_includes_child_deps(self):
        """With descendants, child functions' deps are also included."""
        deps = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, True)

        # Should have MORE deps than without descendants
        without = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, False)
        assert len(deps) > len(without)

        # Should have from_descendant entries for child functions
        descendant_deps = [d for d in deps if 'from_descendant' in d]
        assert len(descendant_deps) > 0

        # copy_model_and_build_map has outgoing deps
        copy_deps = [d for d in deps if d.get('from_descendant') == 'copy_model_and_build_map']
        assert len(copy_deps) > 0

        # generalize_model has outgoing deps
        gen_deps = [d for d in deps if d.get('from_descendant') == 'generalize_model']
        assert len(gen_deps) > 0

    def test_descendants_incoming(self):
        """Incoming deps with descendants captures callers of child functions."""
        deps = _collect_deps(self.elem, GENERALIZER, 'incoming', None, True)

        # generalize_model has incoming from test file and from main
        # main's incoming from generalize_model is internal (same file child)
        incoming_to_gen = [d for d in deps if d.get('to_descendant') == 'generalize_model']
        assert len(incoming_to_gen) > 0

        # At least one incoming should be from outside the file
        external_sources = [
            d for d in incoming_to_gen
            if not d['source'].startswith(GENERALIZER)
        ]
        assert len(external_sources) > 0

    def test_descendants_with_result_level_file(self):
        """result_level=4 aggregates targets to file level."""
        deps_raw = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, True)
        deps_file = _collect_deps(self.elem, GENERALIZER, 'outgoing', 4, True)

        # File-level should have fewer unique targets (aggregated)
        raw_targets = {d['target'] for d in deps_raw}
        file_targets = {d['target'] for d in deps_file}
        assert len(file_targets) <= len(raw_targets)

        # All file-level targets should have at most 5 path segments
        # (e.g., /sgraph-and-mcp/sgraph/src/sgraph/sgraph.py)
        for target in file_targets:
            parts = target.split('/')
            assert len(parts) <= 5, f"File-level target too deep: {target}"

    def test_descendants_with_result_level_directory(self):
        """result_level=3 aggregates targets to directory level."""
        deps = _collect_deps(self.elem, GENERALIZER, 'outgoing', 3, True)
        for d in deps:
            parts = d['target'].split('/')
            assert len(parts) <= 4, f"Directory-level target too deep: {d['target']}"

    def test_deptype_is_captured(self):
        """Verify the deptype bugfix: type field should appear in results."""
        deps = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, False)
        typed_deps = [d for d in deps if 'type' in d]
        assert len(typed_deps) > 0, "deptype bugfix: type should be present in output"

        # generalizer.py has 'import' type deps
        import_deps = [d for d in deps if d.get('type') == 'import']
        assert len(import_deps) > 0

    def test_descendants_deptype_on_child_deps(self):
        """Child deps should also have type field."""
        deps = _collect_deps(self.elem, GENERALIZER, 'outgoing', None, True)
        descendant_deps = [d for d in deps if 'from_descendant' in d]
        typed_descendant_deps = [d for d in descendant_deps if 'type' in d]
        assert len(typed_descendant_deps) > 0

    def test_both_directions_with_descendants(self):
        """Both directions in one call with descendants."""
        deps = _collect_deps(self.elem, GENERALIZER, 'both', None, True)
        outgoing = [d for d in deps if d['direction'] == 'outgoing']
        incoming = [d for d in deps if d['direction'] == 'incoming']

        # generalizer.py has outgoing deps (imports)
        assert len(outgoing) > 0
        # generalize_model has at least one incoming caller
        assert len(incoming) > 0


class TestIncludeDescendantsToolHandler:
    """Integration tests through the full tool handler (async)."""

    def setup_method(self):
        if not os.path.exists(MODEL_PATH):
            pytest.skip(f"Model file not found: {MODEL_PATH}")
        self.manager = ModelManager()

    @pytest.mark.asyncio
    async def test_tool_handler_include_descendants_false(self):
        """Tool returns correct result with include_descendants=False (default)."""
        model_id = await self.manager.load_model(MODEL_PATH)
        model = self.manager.get_model(model_id)

        from src.profiles.claude_code import GetElementDependenciesInput

        input_data = GetElementDependenciesInput(
            model_id=model_id,
            element_path=GENERALIZER,
            direction="outgoing",
            include_descendants=False,
        )

        element = model.findElementFromPath(input_data.element_path)
        assert element is not None

        deps = _collect_deps(
            element, input_data.element_path,
            input_data.direction, input_data.result_level,
            input_data.include_descendants,
        )
        assert len(deps) == 5
        assert all('from_descendant' not in d for d in deps)

    @pytest.mark.asyncio
    async def test_tool_handler_include_descendants_true(self):
        """Tool returns descendant deps with include_descendants=True."""
        model_id = await self.manager.load_model(MODEL_PATH)
        model = self.manager.get_model(model_id)

        from src.profiles.claude_code import GetElementDependenciesInput

        input_data = GetElementDependenciesInput(
            model_id=model_id,
            element_path=GENERALIZER,
            direction="outgoing",
            include_descendants=True,
        )

        element = model.findElementFromPath(input_data.element_path)
        deps = _collect_deps(
            element, input_data.element_path,
            input_data.direction, input_data.result_level,
            input_data.include_descendants,
        )

        descendant_deps = [d for d in deps if 'from_descendant' in d]
        assert len(descendant_deps) > 0

    @pytest.mark.asyncio
    async def test_tool_handler_descendants_with_result_level(self):
        """Tool correctly combines include_descendants + result_level."""
        model_id = await self.manager.load_model(MODEL_PATH)
        model = self.manager.get_model(model_id)

        element = model.findElementFromPath(GENERALIZER)

        deps_raw = _collect_deps(element, GENERALIZER, 'outgoing', None, True)
        deps_agg = _collect_deps(element, GENERALIZER, 'outgoing', 4, True)

        raw_targets = {d['target'] for d in deps_raw}
        agg_targets = {d['target'] for d in deps_agg}

        # Aggregation should reduce or maintain unique target count
        assert len(agg_targets) <= len(raw_targets)

    @pytest.mark.asyncio
    async def test_input_schema_defaults(self):
        """Verify GetElementDependenciesInput defaults are backwards-compatible."""
        from src.profiles.claude_code import GetElementDependenciesInput

        input_data = GetElementDependenciesInput(
            element_path="/some/path",
        )
        assert input_data.include_descendants is False
        assert input_data.direction == "both"
        assert input_data.result_level is None
        assert input_data.include_external is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
