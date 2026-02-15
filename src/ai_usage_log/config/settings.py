"""Configuration: base path, terminal detection, project detection."""

import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path


def get_base_path() -> Path:
    """Return the AI usage log base directory."""
    return Path(os.environ.get("AI_USAGE_LOG_PATH", "~/Documents/ai-usage")).expanduser()


def get_user() -> str:
    """Return current username."""
    return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))


def get_host() -> str:
    """Return hostname (short)."""
    return socket.gethostname().split(".")[0]


def get_terminal_session() -> str:
    """Detect the terminal multiplexer session."""
    if os.environ.get("ZELLIJ"):
        name = os.environ.get("ZELLIJ_SESSION_NAME", "unknown")
        return f"zellij:{name}"

    if os.environ.get("TMUX"):
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"tmux:{result.stdout.strip()}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return "tmux:unknown"

    if os.environ.get("STY"):
        return f"screen:{os.environ['STY']}"

    return "standalone"


def detect_project(cwd: str) -> str | None:
    """Detect git project name from cwd."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def detect_project_root(cwd: str) -> str | None:
    """Detect git project root path from cwd."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def get_now() -> str:
    """Return current time as HH:MM."""
    return datetime.now().strftime("%H:%M")


def get_year_month() -> tuple[str, str]:
    """Return (YYYY, MM) for today."""
    now = datetime.now()
    return now.strftime("%Y"), now.strftime("%m")
