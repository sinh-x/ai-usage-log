"""Project-level ai-sessions reference management."""

from pathlib import Path

from ..models.schemas import ProjectRefResult


class ProjectService:
    """Manages project .claude/ai-sessions-<user>@<host>.md files."""

    def save_project_ref(
        self,
        project_root: str,
        user: str,
        host: str,
        content: str,
    ) -> ProjectRefResult:
        """Write or update the project ai-sessions reference file.

        Args:
            project_root: Absolute path to the git project root.
            user: Username (e.g. 'sinh').
            host: Hostname (e.g. 'Drgnfly').
            content: Full markdown content for the file.
        """
        claude_dir = Path(project_root) / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        filename = f"ai-sessions-{user}@{host}.md"
        filepath = claude_dir / filename
        created = not filepath.exists()
        filepath.write_text(content)

        # Ensure gitignore entry exists
        self._ensure_gitignore(claude_dir)

        return ProjectRefResult(path=str(filepath), created=created)

    @staticmethod
    def _ensure_gitignore(claude_dir: Path) -> None:
        """Ensure .claude/.gitignore ignores ai-sessions-*.md."""
        gitignore = claude_dir / ".gitignore"
        pattern = "ai-sessions-*.md"

        if gitignore.exists():
            content = gitignore.read_text()
            if pattern in content:
                return
            # Append if not present
            if not content.endswith("\n"):
                content += "\n"
            content += f"{pattern}\n"
            gitignore.write_text(content)
        else:
            gitignore.write_text(f"{pattern}\n")

    def get_project_ref(
        self, project_root: str, user: str, host: str
    ) -> str | None:
        """Read existing project reference file, or None."""
        filepath = Path(project_root) / ".claude" / f"ai-sessions-{user}@{host}.md"
        if filepath.exists():
            return filepath.read_text()
        return None
