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

# Import all tool modules to register them
# This imports the tools and they self-register with @mcp.tool() decorators
from src.tools import model_tools, search_tools, analysis_tools, navigation_tools

print("✅ All tool modules loaded successfully")


@mcp.startup()
async def startup():
    """Startup handler to ensure proper initialization"""
    print("🔧 MCP Server starting up...")
    # Add a small delay to ensure all tools are properly registered
    await asyncio.sleep(0.5)
    print("✅ MCP Server startup complete")


@mcp.shutdown()
async def shutdown():
    """Shutdown handler for cleanup"""
    print("🔄 MCP Server shutting down...")


if __name__ == "__main__":
    print("🚀 Starting modular MCP server...")
    print(f"📊 Server will run on http://0.0.0.0:8008")
    print(f"🛠️  Modular server initialized with all tools registered")
    
    # Add initialization delay before starting
    time.sleep(1.0)
    
    mcp.run(transport="sse")
