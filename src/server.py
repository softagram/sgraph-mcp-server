"""
Profile-based MCP server for sgraph-mcp-server.

Supports multiple profiles optimized for different use cases:
- claude-code: AI-assisted software development (5 tools)
- legacy: Original 14-tool set (backwards compatible)

Usage:
    uv run python -m src.server --profile claude-code
    uv run python -m src.server --profile legacy
    uv run python -m src.server  # defaults to legacy
"""

import argparse
import sys
from mcp.server.fastmcp import FastMCP

from src.utils.logging import setup_logging
from src.profiles import get_profile, list_profiles


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SGraph MCP Server with profile support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Profiles:
  claude-code  AI-assisted development (5 tools, optimized for Claude Code)
  legacy       Original 14-tool set (backwards compatible, default)

Examples:
  uv run python -m src.server --profile claude-code
  uv run python -m src.server  # uses legacy profile
        """,
    )
    parser.add_argument(
        "--profile",
        "-p",
        type=str,
        default="legacy",
        choices=list_profiles(),
        help="Profile to use (default: legacy)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8008,
        help="Port to run the server on (default: 8008)",
    )
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        default="sse",
        choices=["sse", "stdio"],
        help="Transport to use (default: sse)",
    )
    parser.add_argument(
        "--auto-load",
        type=str,
        default=None,
        help="Path to a model file to use without an explicit sgraph_load_model call. "
             "Registered at startup, parsed on the first tool call that needs it. "
             "Only the claude-code profile consults it.",
    )
    parser.add_argument(
        "--default-scope",
        type=str,
        default=None,
        help="Default scope path for searches (e.g., '/Organization/Platform/my-service')",
    )
    return parser.parse_args()


def main():
    """Main entry point for the MCP server."""
    # Parse arguments
    args = parse_args()

    # For stdio transport, redirect all output to stderr to avoid corrupting JSON-RPC
    log = sys.stderr if args.transport == "stdio" else sys.stdout

    # Set up logging (must use stderr for stdio transport)
    setup_logging(stream=log)

    # Create MCP server
    mcp = FastMCP("SGraph")
    mcp.settings.port = args.port

    # Load and register the selected profile
    print(f"🔧 Loading profile: {args.profile}", file=log)
    try:
        profile = get_profile(args.profile)
        profile.register_tools(mcp)
        print(f"✅ Profile '{args.profile}' loaded: {profile.description}", file=log)
    except ValueError as e:
        print(f"❌ Error: {e}", file=log)
        return 1

    # Register the model without reading it. The first tool call triggers the parse,
    # so a session that never queries sgraph costs nothing beyond an idle process.
    if args.auto_load:
        from src.profiles.base import get_model_manager
        get_model_manager().set_deferred_model(args.auto_load, args.default_scope)
        print(f"📂 Model registered, loads on first use: {args.auto_load}", file=log, flush=True)
        if args.profile != "claude-code":
            # The legacy tools hold their own ModelManager (src/tools/model_tools.py),
            # so they will never see this one. Say so rather than imply it is armed.
            print(
                f"⚠️ Profile '{args.profile}' ignores --auto-load; "
                "callers must pass model_id from sgraph_load_model",
                file=log, flush=True,
            )
        if args.default_scope:
            print(f"🔍 Default scope: {args.default_scope}", file=log, flush=True)

    # Start the server
    if args.transport == "sse":
        print(f"🚀 Starting MCP server on http://0.0.0.0:{args.port}", file=log)
    else:
        print(f"🚀 Starting MCP server with {args.transport} transport", file=log, flush=True)
    print(f"📊 Profile: {args.profile}", file=log, flush=True)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
