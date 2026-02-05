#!/bin/bash
#
# Install sgraph tools as macOS LaunchAgents
#
# Usage: ./install-watcher.sh
#
# This will:
#   1. Install sgraph-watcher.py and sgraph-mcp to ~/.local/bin/
#   2. Configure launchd plist with correct paths
#   3. Install and load the LaunchAgent
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
LOG_DIR="$HOME/.config/sgraph"
PLIST_NAME="com.sgraph.watcher.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "Installing sgraph tools..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$LAUNCH_AGENTS"

# Copy the watcher script
cp "$SCRIPT_DIR/sgraph-watcher.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/sgraph-watcher.py"
echo "✓ Installed sgraph-watcher.py to $INSTALL_DIR/"

# Copy the MCP launcher
cp "$SCRIPT_DIR/sgraph-mcp" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/sgraph-mcp"
echo "✓ Installed sgraph-mcp to $INSTALL_DIR/"

# Create the plist with correct paths
cat > "$LAUNCH_AGENTS/$PLIST_NAME" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sgraph.watcher</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>python3</string>
        <string>$INSTALL_DIR/sgraph-watcher.py</string>
        <string>start</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/watcher.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/watcher.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.local/bin</string>
    </dict>

    <key>ThrottleInterval</key>
    <integer>60</integer>
</dict>
</plist>
EOF
echo "✓ Created LaunchAgent plist"

# Unload existing service if running
if launchctl list | grep -q "com.sgraph.watcher"; then
    echo "Unloading existing service..."
    launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
fi

# Load the new service
launchctl load "$LAUNCH_AGENTS/$PLIST_NAME"
echo "✓ Loaded LaunchAgent"

# Create convenience symlink
if [ ! -L "$HOME/.local/bin/sgraph-watcher" ]; then
    ln -sf "$INSTALL_DIR/sgraph-watcher.py" "$HOME/.local/bin/sgraph-watcher"
    echo "✓ Created symlink: sgraph-watcher"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Commands:"
echo "  sgraph-mcp                      # Start MCP server (claude-code profile)"
echo "  sgraph-watcher status           # Check watcher status"
echo "  sgraph-watcher add <path>       # Add project to watch"
echo "  sgraph-watcher list             # List watched projects"
echo "  sgraph-watcher analyze <path>   # Force immediate analysis"
echo ""
echo "The watcher will start automatically at login."
echo "Current status:"
"$INSTALL_DIR/sgraph-watcher.py" status
