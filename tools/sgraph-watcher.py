#!/usr/bin/env python3
"""
sgraph-watcher: File system watcher for automatic code analysis.

Watches project directories for changes and triggers analysis when files change.
Uses debouncing (3 min) to avoid excessive re-analysis.

Usage:
    sgraph-watcher start                    # Start daemon (foreground)
    sgraph-watcher add <project-path>       # Add project to watch list
    sgraph-watcher remove <project-path>    # Remove project from watch list
    sgraph-watcher list                     # List watched projects
    sgraph-watcher status                   # Show watcher status
    sgraph-watcher analyze <project-path>   # Force immediate analysis
"""

import argparse
import json
import os
import subprocess
import sys
import time
import signal
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Config paths
CONFIG_DIR = Path.home() / ".config" / "sgraph"
CONFIG_FILE = CONFIG_DIR / "watcher.json"
PID_FILE = CONFIG_DIR / "watcher.pid"
LOG_FILE = CONFIG_DIR / "watcher.log"

# Settings
DEBOUNCE_SECONDS = 180  # 3 minutes
IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes
ANALYZE_SCRIPT = Path.home() / "analyze.sh"
OUTPUT_BASE = Path("/tmp/analysis-outputs")

# File patterns to watch (common code files)
WATCH_PATTERNS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala",
    ".xml", ".json", ".yaml", ".yml", ".toml", ".sql"
}

# Patterns to ignore
IGNORE_PATTERNS = {
    "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv",
    ".idea", ".vscode", ".pytest_cache", "dist", "build", ".tox",
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so"
}


def log(message: str):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def load_config() -> dict:
    """Load watcher configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"projects": {}}


def save_config(config: dict):
    """Save watcher configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_project_name(project_path: Path) -> str:
    """Get project name from path."""
    return project_path.name


def get_output_dir(project_path: Path) -> Path:
    """Get output directory for a project."""
    return OUTPUT_BASE / get_project_name(project_path)


def get_model_path(project_path: Path) -> Path:
    """Get the latest.xml.zip path for a project."""
    return get_output_dir(project_path) / "latest.xml.zip"


def should_watch_file(filepath: Path) -> bool:
    """Check if a file should trigger re-analysis."""
    # Check ignore patterns
    for part in filepath.parts:
        if part in IGNORE_PATTERNS:
            return False
        for pattern in IGNORE_PATTERNS:
            if pattern.startswith("*") and part.endswith(pattern[1:]):
                return False

    # Check if it's a code file
    return filepath.suffix.lower() in WATCH_PATTERNS


def get_latest_change_time(project_path: Path) -> Optional[datetime]:
    """Get the most recent modification time of watched files."""
    latest = None
    try:
        for root, dirs, files in os.walk(project_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS]

            for file in files:
                filepath = Path(root) / file
                if should_watch_file(filepath):
                    try:
                        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                        if latest is None or mtime > latest:
                            latest = mtime
                    except (OSError, IOError):
                        pass
    except Exception as e:
        log(f"Error scanning {project_path}: {e}")
    return latest


def get_model_time(project_path: Path) -> Optional[datetime]:
    """Get the modification time of the model file."""
    model_path = get_model_path(project_path)
    if model_path.exists():
        # Follow symlink to get actual file time
        real_path = model_path.resolve()
        if real_path.exists():
            return datetime.fromtimestamp(real_path.stat().st_mtime)
    return None


def is_model_stale(project_path: Path) -> bool:
    """Check if the model is stale (older than latest code change)."""
    model_time = get_model_time(project_path)
    if model_time is None:
        return True  # No model = stale

    latest_change = get_latest_change_time(project_path)
    if latest_change is None:
        return False  # No code files = not stale

    return latest_change > model_time


def run_analysis(project_path: Path) -> bool:
    """Run analysis for a project."""
    output_dir = get_output_dir(project_path)

    log(f"Starting analysis: {project_path}")

    try:
        result = subprocess.run(
            [str(ANALYZE_SCRIPT), str(project_path), "--output-dir", str(output_dir)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            log(f"Analysis complete: {project_path}")
            return True
        else:
            log(f"Analysis failed: {project_path}")
            log(f"stderr: {result.stderr[-500:]}")
            return False

    except subprocess.TimeoutExpired:
        log(f"Analysis timeout: {project_path}")
        return False
    except Exception as e:
        log(f"Analysis error: {project_path}: {e}")
        return False


class ProjectWatcher:
    """Watches a single project for changes."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.last_change_detected = None
        self.last_analysis_time = None
        self.pending_analysis = False

    def check_for_changes(self) -> bool:
        """Check if project has changes that need analysis."""
        if not is_model_stale(self.project_path):
            return False

        now = datetime.now()

        # If we haven't detected a change yet, record it
        if self.last_change_detected is None:
            self.last_change_detected = now
            self.pending_analysis = True
            log(f"Change detected: {self.project_path}")
            return False  # Wait for debounce

        # Check if debounce period has passed
        debounce_elapsed = (now - self.last_change_detected).total_seconds()
        if debounce_elapsed < DEBOUNCE_SECONDS:
            return False  # Still in debounce period

        # Check if we've already analyzed recently
        if self.last_analysis_time:
            since_analysis = (now - self.last_analysis_time).total_seconds()
            if since_analysis < DEBOUNCE_SECONDS:
                return False  # Recently analyzed

        return self.pending_analysis

    def mark_analyzed(self):
        """Mark that analysis was performed."""
        self.last_analysis_time = datetime.now()
        self.last_change_detected = None
        self.pending_analysis = False


class WatcherDaemon:
    """Main watcher daemon."""

    def __init__(self):
        self.running = False
        self.watchers: dict[str, ProjectWatcher] = {}
        self.last_activity = datetime.now()

    def load_projects(self):
        """Load projects from config."""
        config = load_config()
        for project_path_str in config.get("projects", {}):
            project_path = Path(project_path_str)
            if project_path.exists():
                self.watchers[project_path_str] = ProjectWatcher(project_path)
                log(f"Watching: {project_path}")

    def run(self):
        """Main daemon loop."""
        self.running = True
        self.load_projects()

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        log(f"Watcher started (PID {os.getpid()})")
        log(f"Watching {len(self.watchers)} projects")
        log(f"Debounce: {DEBOUNCE_SECONDS}s, Idle timeout: {IDLE_TIMEOUT_SECONDS}s")

        # Signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            while self.running:
                self._check_all_projects()
                self._check_idle_timeout()
                time.sleep(10)  # Check every 10 seconds
        finally:
            self._cleanup()

    def _handle_signal(self, signum, frame):
        log(f"Received signal {signum}, shutting down...")
        self.running = False

    def _check_all_projects(self):
        """Check all projects for changes."""
        for project_path_str, watcher in self.watchers.items():
            if watcher.check_for_changes():
                self.last_activity = datetime.now()
                if run_analysis(watcher.project_path):
                    watcher.mark_analyzed()

    def _check_idle_timeout(self):
        """Check if we've been idle too long."""
        idle_time = (datetime.now() - self.last_activity).total_seconds()
        if idle_time > IDLE_TIMEOUT_SECONDS:
            log(f"Idle timeout ({IDLE_TIMEOUT_SECONDS}s), shutting down...")
            self.running = False

    def _cleanup(self):
        """Cleanup on exit."""
        if PID_FILE.exists():
            PID_FILE.unlink()
        log("Watcher stopped")


# CLI Commands

def cmd_start(args):
    """Start the watcher daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)  # Check if process exists
            print(f"Watcher already running (PID {pid})")
            return 1
        except ProcessLookupError:
            PID_FILE.unlink()  # Stale PID file

    daemon = WatcherDaemon()
    daemon.run()
    return 0


def cmd_stop(args):
    """Stop the watcher daemon."""
    if not PID_FILE.exists():
        print("Watcher not running")
        return 1

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped watcher (PID {pid})")
        return 0
    except ProcessLookupError:
        PID_FILE.unlink()
        print("Watcher was not running (stale PID file removed)")
        return 1


def cmd_status(args):
    """Show watcher status."""
    config = load_config()
    projects = config.get("projects", {})

    # Check if daemon is running
    running = False
    pid = None
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            running = True
        except ProcessLookupError:
            pass

    print(f"Watcher: {'running' if running else 'stopped'}" + (f" (PID {pid})" if running else ""))
    print(f"Projects: {len(projects)}")
    print(f"Config: {CONFIG_FILE}")
    print(f"Log: {LOG_FILE}")
    print()

    if projects:
        print("Watched projects:")
        for project_path_str in projects:
            project_path = Path(project_path_str)
            model_path = get_model_path(project_path)
            model_exists = model_path.exists()
            stale = is_model_stale(project_path) if project_path.exists() else None

            status = "✅ fresh" if model_exists and not stale else "⚠️ stale" if model_exists else "❌ no model"
            print(f"  {project_path_str}: {status}")

    return 0


def cmd_add(args):
    """Add a project to watch list."""
    project_path = Path(args.project_path).resolve()

    if not project_path.exists():
        print(f"Error: {project_path} does not exist")
        return 1

    config = load_config()
    if "projects" not in config:
        config["projects"] = {}

    project_path_str = str(project_path)
    if project_path_str in config["projects"]:
        print(f"Already watching: {project_path}")
        return 0

    config["projects"][project_path_str] = {
        "added": datetime.now().isoformat(),
        "name": get_project_name(project_path)
    }
    save_config(config)

    print(f"Added: {project_path}")
    print(f"Output: {get_output_dir(project_path)}")
    print()
    print("Restart watcher to pick up changes: sgraph-watcher stop && sgraph-watcher start &")
    return 0


def cmd_remove(args):
    """Remove a project from watch list."""
    project_path = Path(args.project_path).resolve()
    project_path_str = str(project_path)

    config = load_config()
    if project_path_str not in config.get("projects", {}):
        print(f"Not watching: {project_path}")
        return 1

    del config["projects"][project_path_str]
    save_config(config)

    print(f"Removed: {project_path}")
    return 0


def cmd_list(args):
    """List watched projects."""
    config = load_config()
    projects = config.get("projects", {})

    if not projects:
        print("No projects being watched")
        print()
        print("Add a project: sgraph-watcher add /path/to/project")
        return 0

    for project_path_str, info in projects.items():
        project_path = Path(project_path_str)
        model_time = get_model_time(project_path)
        model_str = model_time.strftime("%Y-%m-%d %H:%M") if model_time else "none"
        print(f"{project_path_str}")
        print(f"  Model: {model_str}")
        print(f"  Output: {get_output_dir(project_path)}")

    return 0


def cmd_analyze(args):
    """Force immediate analysis of a project."""
    project_path = Path(args.project_path).resolve()

    if not project_path.exists():
        print(f"Error: {project_path} does not exist")
        return 1

    print(f"Analyzing: {project_path}")
    success = run_analysis(project_path)
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(
        description="sgraph-watcher: Automatic code analysis on file changes"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # start
    subparsers.add_parser("start", help="Start watcher daemon (foreground)")

    # stop
    subparsers.add_parser("stop", help="Stop watcher daemon")

    # status
    subparsers.add_parser("status", help="Show watcher status")

    # add
    add_parser = subparsers.add_parser("add", help="Add project to watch list")
    add_parser.add_argument("project_path", help="Path to project")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove project from watch list")
    remove_parser.add_argument("project_path", help="Path to project")

    # list
    subparsers.add_parser("list", help="List watched projects")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Force immediate analysis")
    analyze_parser.add_argument("project_path", help="Path to project")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "analyze": cmd_analyze,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
