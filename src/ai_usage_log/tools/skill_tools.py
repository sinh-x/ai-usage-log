"""Tool: get_skill — returns bundled skill files for agent-driven installation."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP


_PACKAGE_DIR = Path(__file__).resolve().parent.parent

# Try two locations: package-internal (pip install) then project-root (dev)
_SKILL_CANDIDATES = [
    _PACKAGE_DIR / "skill_data",                         # inside package
    _PACKAGE_DIR.parent.parent / "skill" / "ai-usage-log",  # project root
]


def _find_skill_dir() -> Path | None:
    for candidate in _SKILL_CANDIDATES:
        if candidate.is_dir() and (candidate / "SKILL.md").exists():
            return candidate
    return None


def register(mcp: FastMCP) -> None:
    """Register skill tools."""

    @mcp.tool(
        name="get_skill",
        annotations={
            "title": "Get Installable Skill",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_skill() -> str:
        """Return the bundled ai-usage-log skill files for installation.

        Returns a JSON object with:
        - install_path: recommended installation directory (~/.claude/skills/ai-usage-log/)
        - files: dict of relative_path → file content
        - instructions: brief install guidance for the agent

        The agent can use these contents to write the skill files
        to the user's system using its own file-writing capabilities.
        """
        skill_dir = _find_skill_dir()

        if skill_dir is None:
            return json.dumps({
                "error": "Skill files not found in any expected location.",
                "checked": [str(p) for p in _SKILL_CANDIDATES],
            })

        files: dict[str, str] = {}
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(skill_dir))
                try:
                    files[rel] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    files[rel] = f"<binary file, {path.stat().st_size} bytes>"

        return json.dumps({
            "install_path": "~/.claude/skills/ai-usage-log",
            "files": files,
            "instructions": (
                "Write each file to the install_path directory. "
                "Create subdirectories as needed (e.g., assets/). "
                "The SKILL.md file must be at the root of the skill directory. "
                "After writing, the skill is automatically detected by Claude Code."
            ),
        }, indent=2)
