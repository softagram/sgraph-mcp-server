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
        help="Path to model file to load automatically at startup",
    )
    parser.add_argument(
        "--default-scope",
        type=str,
        default=None,
        help="Default scope path for searches (e.g., '/TalenomSoftware/Online/talenom.online.invoicepayment5.api')",
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

    # Auto-load model in background thread (to avoid blocking MCP protocol startup)
    if args.auto_load:
        import threading
        def _bg_load():
            print(f"📂 Auto-loading model (background): {args.auto_load}", file=log, flush=True)
            try:
                from src.profiles.base import get_model_manager
                mm = get_model_manager()
                if args.default_scope:
                    mm.default_scope = args.default_scope
                model_id = mm.load_model_sync(args.auto_load)
                print(f"✅ Model ready: {model_id}", file=log, flush=True)
                if args.default_scope:
                    print(f"🔍 Default scope: {args.default_scope}", file=log, flush=True)
            except Exception as e:
                print(f"⚠️ Auto-load failed: {e}", file=log, flush=True)
        threading.Thread(target=_bg_load, daemon=True).start()

    # Start the server
    if args.transport == "sse":
        print(f"🚀 Starting MCP server on http://0.0.0.0:{args.port}", file=log)
    else:
        print(f"🚀 Starting MCP server with {args.transport} transport", file=log, flush=True)
    print(f"📊 Profile: {args.profile}", file=log, flush=True)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
