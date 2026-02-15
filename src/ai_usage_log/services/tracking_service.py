"""Batch tracking file updates."""

from pathlib import Path

from ..models.schemas import StatsResult, TrackingResult


class TrackingService:
    """Manages tracking files (learning, skills, verification, quiz, stats)."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def update_tracking(self, updates: dict[str, str]) -> TrackingResult:
        """Batch update tracking files.

        Args:
            updates: Dict of filename -> new full content.
                     Valid keys: learning-queue.md, skills-gained.md,
                     verification-queue.md, quiz-bank.md, statistics.md
        """
        valid_files = {
            "learning-queue.md",
            "skills-gained.md",
            "verification-queue.md",
            "quiz-bank.md",
            "statistics.md",
        }
        updated: list[str] = []

        for filename, content in updates.items():
            if filename not in valid_files:
                continue
            filepath = self.base_path / filename
            filepath.write_text(content)
            updated.append(filename)

        return TrackingResult(updated_files=updated)

    def get_stats(self) -> StatsResult:
        """Read the statistics.md file."""
        filepath = self.base_path / "statistics.md"
        if not filepath.exists():
            return StatsResult(content="", path=str(filepath))
        return StatsResult(content=filepath.read_text(), path=str(filepath))

    def get_tracking_file(self, filename: str) -> str:
        """Read a tracking file by name."""
        valid_files = {
            "learning-queue.md",
            "skills-gained.md",
            "verification-queue.md",
            "quiz-bank.md",
            "statistics.md",
        }
        if filename not in valid_files:
            raise ValueError(f"Invalid tracking file: {filename}")
        filepath = self.base_path / filename
        if not filepath.exists():
            return ""
        return filepath.read_text()
