#!/usr/bin/env python3
"""
The stdio server must survive requests it does not understand.

Claude Code 2.1.x opens every stdio connection with a `server/discover` probe
before `initialize`. MCP SDK 1.9 failed request validation on the unknown method
and let the ExceptionGroup take the whole process down, so Claude Code saw the
server exit, waited out its probe timeout and restarted it without the probe.
Every session paid ~3 s for that, and a second failure would have left it with
no sgraph tools at all.
"""

import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

DISCOVER = {"jsonrpc": "2.0", "id": 0, "method": "server/discover", "params": {"_meta": {}}}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "stdio-protocol-test", "version": "0"},
    },
}


def _start_server() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "src.server", "--profile", "claude-code", "--transport", "stdio"],
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _send(proc: subprocess.Popen, message: dict) -> None:
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def test_an_unknown_method_before_initialize_does_not_kill_the_server():
    proc = _start_server()
    try:
        _send(proc, DISCOVER)
        _send(proc, INITIALIZE)
        # Closing stdin ends the session once the queued requests are answered,
        # so communicate() returns instead of hanging on a live server.
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()

    replies = {}
    for line in stdout.splitlines():
        message = json.loads(line)
        if "id" in message:
            replies[message["id"]] = message

    assert 1 in replies, f"no reply to initialize; server stderr:\n{stderr[-2000:]}"
    assert "result" in replies[1], replies[1]
    assert replies[1]["result"]["serverInfo"]["name"] == "SGraph"
    # The probe itself gets an error reply rather than silence.
    assert 0 in replies and "error" in replies[0], replies.get(0)
