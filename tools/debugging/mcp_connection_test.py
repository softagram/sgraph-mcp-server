#!/usr/bin/env python3
"""
MCP connection testing utility.

Tests MCP server connectivity, tool availability, and basic functionality.
Useful for debugging MCP timing issues and server problems.
"""

import asyncio
import subprocess
import time
import json
import sys
from pathlib import Path


def check_server_port(port: int = 8008):
    """Check if a server is running on the specified port."""
    
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and "LISTEN" in result.stdout:
            return True, f"Server running on port {port}"
        else:
            return False, f"No server found on port {port}"
            
    except Exception as e:
        return False, f"Error checking port: {str(e)}"


def test_http_connectivity(url: str, timeout: int = 5):
    """Test basic HTTP connectivity to the server."""
    
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        return result.returncode == 0, result.stdout[:200] if result.stdout else result.stderr[:200]
        
    except subprocess.TimeoutExpired:
        return False, "HTTP request timed out"
    except Exception as e:
        return False, f"HTTP test error: {str(e)}"


def check_nodejs_version():
    """Check Node.js version for mcp-remote compatibility."""
    
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            # Extract version number
            version_num = version.replace('v', '').split('.')[0]
            
            if int(version_num) >= 20:
                return True, f"Node.js {version} (✅ Compatible)"
            else:
                return False, f"Node.js {version} (❌ Requires v20+)"
        else:
            return False, "Node.js not found"
            
    except Exception as e:
        return False, f"Node.js check error: {str(e)}"


def test_mcp_remote_connection(server_url: str, timeout: int = 10):
    """Test mcp-remote connection to the server."""
    
    try:
        # Test with a simple tools list request
        test_request = {"method": "tools/list", "params": {}}
        
        cmd = [
            "npx", "mcp-remote", server_url,
            "--timeout", str(timeout * 1000)  # mcp-remote expects milliseconds
        ]
        
        result = subprocess.run(
            cmd,
            input=json.dumps(test_request),
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        
        if result.returncode == 0:
            # Try to parse the output to count tools
            try:
                # Look for tool count in output
                lines = result.stdout.split('\n')
                tool_count = 0
                for line in lines:
                    if 'tools' in line.lower() and 'name' in line:
                        tool_count += 1
                
                return True, f"MCP connection successful ({tool_count} tools found)"
            except:
                return True, "MCP connection successful (couldn't parse tool count)"
        else:
            return False, f"MCP connection failed: {result.stderr[:200]}"
            
    except subprocess.TimeoutExpired:
        return False, "MCP connection timed out"
    except Exception as e:
        return False, f"MCP test error: {str(e)}"


async def run_connection_diagnostics(server_url: str = "http://localhost:8008/sse"):
    """Run comprehensive MCP connection diagnostics."""
    
    print("🔧 MCP CONNECTION DIAGNOSTICS")
    print("=" * 50)
    
    port = 8008  # Extract from URL or default
    if ":" in server_url:
        try:
            port = int(server_url.split(":")[-1].split("/")[0])
        except:
            pass
    
    diagnostics = {}
    
    # 1. Check server port
    print("1️⃣  Checking server port...")
    is_running, message = check_server_port(port)
    diagnostics["server_port"] = {"status": is_running, "message": message}
    print(f"   {message}")
    
    # 2. Test HTTP connectivity
    print("\n2️⃣  Testing HTTP connectivity...")
    http_ok, http_message = test_http_connectivity(server_url.replace("/sse", ""))
    diagnostics["http_connectivity"] = {"status": http_ok, "message": http_message}
    print(f"   HTTP: {'✅' if http_ok else '❌'} {http_message}")
    
    # 3. Check Node.js version
    print("\n3️⃣  Checking Node.js version...")
    node_ok, node_message = check_nodejs_version()
    diagnostics["nodejs_version"] = {"status": node_ok, "message": node_message}
    print(f"   {node_message}")
    
    # 4. Test MCP connection (only if server is running)
    print("\n4️⃣  Testing MCP connection...")
    if is_running:
        mcp_ok, mcp_message = test_mcp_remote_connection(server_url)
        diagnostics["mcp_connection"] = {"status": mcp_ok, "message": mcp_message}
        print(f"   {mcp_message}")
    else:
        diagnostics["mcp_connection"] = {"status": False, "message": "Skipped (server not running)"}
        print("   Skipped (server not running)")
    
    # Summary
    print(f"\n📊 DIAGNOSTIC SUMMARY")
    print("-" * 30)
    
    all_good = True
    for check, result in diagnostics.items():
        status_icon = "✅" if result["status"] else "❌"
        print(f"{status_icon} {check.replace('_', ' ').title()}")
        if not result["status"]:
            all_good = False
    
    if all_good:
        print("\n🎉 All diagnostics passed! MCP connection should work.")
    else:
        print("\n⚠️  Some issues found. See messages above for details.")
        
        # Provide troubleshooting suggestions
        print("\n🔧 TROUBLESHOOTING SUGGESTIONS:")
        
        if not diagnostics["server_port"]["status"]:
            print("• Start the server: uv run src/server_modular.py")
            
        if not diagnostics["nodejs_version"]["status"]:
            print("• Install Node.js v20+: https://nodejs.org/")
            print("• Or use nvm: nvm install 20 && nvm use 20")
            
        if not diagnostics["mcp_connection"]["status"] and diagnostics["server_port"]["status"]:
            print("• Try restarting the server")
            print("• Check server logs for errors")
            print("• Ensure mcp-remote is installed: npm install -g mcp-remote")
    
    return all_good, diagnostics


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP connection")
    parser.add_argument(
        "--url", 
        default="http://localhost:8008/sse",
        help="MCP server URL"
    )
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    success, diagnostics = await run_connection_diagnostics(args.url)
    
    if args.json:
        print(json.dumps(diagnostics, indent=2))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

