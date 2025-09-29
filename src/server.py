"""
Modular MCP server for sgraph-mcp-server.

Clean server setup that imports tools from separate modules.
"""

import asyncio
import time
from mcp.server.fastmcp import FastMCP

from src.utils.logging import setup_logging

# Set up logging
setup_logging()

# Create MCP server
mcp = FastMCP("SGraph")
mcp.settings.port = 8008

# Initialize the components
print("🔧 Initializing modular components...")

# Import tool modules and register them with the MCP server
from src.tools import model_tools, search_tools, analysis_tools, navigation_tools

# Register all tools with the MCP server
model_tools.register_tools(mcp)
search_tools.register_tools(mcp)
analysis_tools.register_tools(mcp)
navigation_tools.register_tools(mcp)

print("✅ All tool modules loaded successfully")


def main():
    """Main entry point for the MCP server."""
    print("🚀 Starting modular MCP server...")
    print(f"📊 Server will run on http://0.0.0.0:8008")
    print(f"🛠️  Modular server initialized with all tools registered")
    
    # Add initialization delay before starting
    time.sleep(1.0)
    
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
