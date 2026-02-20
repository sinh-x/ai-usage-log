"""Directory structure creation and tracking file initialization."""

from pathlib import Path

from ..models.schemas import StructureResult
from ..templates.file_templates import TRACKING_FILES


class StructureService:
    """Creates and manages the ai-usage directory tree."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def init_structure(self, year: str, month: str) -> StructureResult:
        """Create directory structure and tracking files. Idempotent."""
        created_dirs: list[str] = []
        created_files: list[str] = []
        already_existed = self.base_path.exists()

        # Required directories
        dirs = [
            self.base_path / "sessions" / year / month,
            self.base_path / "daily" / year / month,
            self.base_path / "insights" / "weekly",
            self.base_path / "insights" / "monthly",
            self.base_path / "statistics",
        ]

        for d in dirs:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(d))

        # Tracking files (only create if missing)
        for filename, content in TRACKING_FILES.items():
            filepath = self.base_path / filename
            if not filepath.exists():
                filepath.write_text(content)
                created_files.append(str(filepath))

        return StructureResult(
            base_path=str(self.base_path),
            created_dirs=created_dirs,
            created_files=created_files,
            already_existed=already_existed,
        )
