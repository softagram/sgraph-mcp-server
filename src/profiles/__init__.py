"""
Profile registry for sgraph-mcp-server.

Profiles define which tools are available for different use cases:
- claude-code: Optimized for Claude Code IDE
- legacy: Original 14-tool set (backwards compatibility)
"""

from typing import Protocol, Callable
from mcp.server.fastmcp import FastMCP


class Profile(Protocol):
    """Protocol for profile implementations."""

    name: str
    description: str

    def register_tools(self, mcp: FastMCP) -> None:
        """Register this profile's tools with the MCP server."""
        ...


# Profile registry
_profiles: dict[str, Callable[[], Profile]] = {}


def register_profile(name: str):
    """Decorator to register a profile class."""
    def decorator(cls):
        _profiles[name] = cls
        return cls
    return decorator


def get_profile(name: str) -> Profile:
    """Get a profile instance by name."""
    if name not in _profiles:
        available = ", ".join(_profiles.keys())
        raise ValueError(f"Unknown profile: {name}. Available: {available}")
    return _profiles[name]()


def list_profiles() -> list[str]:
    """List available profile names."""
    return list(_profiles.keys())


# Import profiles to trigger registration
from . import base  # noqa: F401, E402
from . import claude_code  # noqa: F401, E402
from . import legacy  # noqa: F401, E402
