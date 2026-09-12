#!/usr/bin/env python3
"""
Unit tests for deferred (lazy) auto-load of the startup model.

A session that never calls an sgraph tool must not pay for parsing the model, so
the model configured with --auto-load is parsed on first use rather than at
process start. Parsing is expensive in both directions: a 112 MB model measured
at 635 MB of heap and 7 s of CPU, and every Claude Code session gets its own
stdio server.
"""

import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.model_manager import ModelManager

MINI_MODEL = """<model version="2.1">
  <elements>
    <e n="src" t="dir">
      <e n="a.py" t="file"/>
    </e>
  </elements>
</model>
"""


class CountingLoader:
    """Wraps the real loader so a test can see how many parses actually happened.

    Parsing stays real - only the call count and an optional delay are added, so
    a test can observe an in-flight parse.
    """

    def __init__(self, real_loader, delay: float = 0.0):
        self._real = real_loader
        self._delay = delay
        self.calls = 0

    def load_model(self, path):
        self.calls += 1
        if self._delay:
            time.sleep(self._delay)
        return self._real.load_model(path)


class FailingLoader:
    """Fails after a delay, so a test can queue callers behind a slow failure."""

    def __init__(self, delay: float = 0.0):
        self._delay = delay
        self.calls = 0

    def load_model(self, path):
        self.calls += 1
        if self._delay:
            time.sleep(self._delay)
        raise RuntimeError("parse exploded")


@pytest.fixture
def model_file(tmp_path):
    path = tmp_path / "mini_model.xml"
    path.write_text(MINI_MODEL)
    return str(path)


class TestDeferredModelLoad:
    """Behaviour of the deferred startup model."""

    def setup_method(self):
        self.manager = ModelManager()

    def _count_parses(self, delay: float = 0.0) -> CountingLoader:
        counting = CountingLoader(self.manager._loader, delay=delay)
        self.manager._loader = counting
        return counting

    # --- configuring costs nothing -------------------------------------------

    def test_configuring_a_deferred_model_parses_nothing(self, model_file):
        self.manager.set_deferred_model(model_file)

        assert self.manager._models == {}
        assert self.manager.default_model_id is None

    def test_configuring_a_deferred_model_records_the_scope(self, model_file):
        self.manager.set_deferred_model(model_file, default_scope="/src")

        assert self.manager.default_scope == "/src"

    # --- first use loads ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_first_use_loads_the_model(self, model_file):
        self.manager.set_deferred_model(model_file)

        model_id = await self.manager.ensure_default_model()

        assert model_id is not None
        assert model_id == self.manager.default_model_id
        assert self.manager.get_model(model_id) is not None

    @pytest.mark.asyncio
    async def test_ensure_returns_an_already_loaded_model_without_reloading(self, model_file):
        counting = self._count_parses()
        self.manager.set_deferred_model(model_file)
        first = await self.manager.ensure_default_model()

        assert await self.manager.ensure_default_model() == first
        assert counting.calls == 1

    @pytest.mark.asyncio
    async def test_ensure_is_a_no_op_without_a_configured_model(self):
        assert await self.manager.ensure_default_model() is None
        assert self.manager._models == {}

    # --- one parse, never several --------------------------------------------

    @pytest.mark.asyncio
    async def test_concurrent_first_use_parses_once(self, model_file):
        counting = self._count_parses(delay=0.2)
        self.manager.set_deferred_model(model_file)

        ids = await asyncio.gather(
            *(self.manager.ensure_default_model() for _ in range(5))
        )

        assert len(set(ids)) == 1
        assert ids[0] is not None
        assert counting.calls == 1

    @pytest.mark.asyncio
    async def test_a_cancelled_caller_does_not_trigger_a_second_parse(self, model_file):
        """A tool call cancelled by the client must not abandon a parse in flight.

        Without this the next call starts a second parse of the same model, and
        two concurrent multi-gigabyte parses are exactly what this change exists
        to prevent.
        """
        counting = self._count_parses(delay=0.3)
        self.manager.set_deferred_model(model_file)

        first = asyncio.create_task(self.manager.ensure_default_model())
        await asyncio.sleep(0.05)  # let the parse get under way
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        model_id = await self.manager.ensure_default_model()

        assert model_id is not None
        assert counting.calls == 1

    # --- failure is reported, not raised --------------------------------------

    @pytest.mark.asyncio
    async def test_a_failing_load_reports_a_structured_error_instead_of_raising(self, tmp_path):
        missing = str(tmp_path / "absent.xml")
        self.manager.set_deferred_model(missing)

        assert await self.manager.ensure_default_model() is None
        assert missing in self.manager.no_model_error()

    def test_the_no_model_error_asks_for_a_load_when_nothing_is_configured(self):
        assert "sgraph_load_model" in self.manager.no_model_error()

    @pytest.mark.asyncio
    async def test_a_failing_load_stays_retryable(self, tmp_path, model_file):
        missing = str(tmp_path / "absent.xml")
        self.manager.set_deferred_model(missing)
        assert await self.manager.ensure_default_model() is None

        # A failed load must not latch the manager into a permanently broken state.
        self.manager.set_deferred_model(model_file)

        assert await self.manager.ensure_default_model() is not None
        assert "sgraph_load_model" in self.manager.no_model_error()

    # --- the event loop keeps running ----------------------------------------

    @pytest.mark.asyncio
    async def test_loading_does_not_block_the_event_loop(self, model_file):
        """The parse runs off the event loop, so other coroutines keep progressing."""
        self._count_parses(delay=0.2)
        self.manager.set_deferred_model(model_file)
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(ticker())
        await self.manager.ensure_default_model()
        beat.cancel()

        assert ticks > 5

    @pytest.mark.asyncio
    async def test_concurrent_callers_do_not_each_retry_a_failing_load(self, model_file):
        """A slow failure must cost one parse, not one per queued caller.

        Serialising waiters behind a lock and letting each one observe a finished,
        failed task turns 5 queued tool calls into 5 sequential parses - the very
        "expensive parse multiplied by concurrency" cost this change removes.
        """
        failing = FailingLoader(delay=0.2)
        self.manager._loader = failing
        self.manager.set_deferred_model(model_file)

        results = await asyncio.gather(
            *(self.manager.ensure_default_model() for _ in range(5))
        )

        assert results == [None] * 5
        assert failing.calls == 1

    @pytest.mark.asyncio
    async def test_a_later_call_retries_the_same_path_after_a_failure(self, model_file):
        """The runtime retry path: same configured path, no re-registration."""
        failing = FailingLoader()
        self.manager._loader = failing
        self.manager.set_deferred_model(model_file)
        assert await self.manager.ensure_default_model() is None

        assert await self.manager.ensure_default_model() is None
        assert failing.calls == 2

    @pytest.mark.asyncio
    async def test_a_cancelled_caller_leaves_no_unretrieved_exception(self, model_file):
        """A parse nobody awaits must not warn about an unretrieved exception."""
        failing = FailingLoader(delay=0.3)
        self.manager._loader = failing
        self.manager.set_deferred_model(model_file)

        caller = asyncio.create_task(self.manager.ensure_default_model())
        await asyncio.sleep(0.05)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller

        await asyncio.sleep(0.4)

        # Nobody is left to observe the failure, so the manager must report it
        # itself rather than let asyncio surface it at garbage-collection time.
        assert "parse exploded" in self.manager.no_model_error()

    def test_configuring_a_missing_model_is_reported_immediately(self, tmp_path):
        """A typo'd --auto-load used to fail loudly at startup; keep that signal."""
        missing = str(tmp_path / "absent.xml.zip")

        self.manager.set_deferred_model(missing)

        assert missing in self.manager.no_model_error()
