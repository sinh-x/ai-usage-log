"""Content resolution: inline string or file-path based."""

from pathlib import Path


def resolve_content(content: str, content_path: str) -> str:
    """Return content from a file path or inline string.

    If ``content_path`` is provided it takes precedence — the file is read and
    returned.  Otherwise ``content`` is used directly.  At least one must be
    non-empty.

    Args:
        content: Inline markdown content (may be empty if *content_path* given).
        content_path: Filesystem path to read content from (may be empty).

    Returns:
        The resolved content string.

    Raises:
        ValueError: If both *content* and *content_path* are empty.
        FileNotFoundError: If *content_path* does not exist.
    """
    if content_path:
        path = Path(content_path)
        if not path.is_file():
            raise FileNotFoundError(f"content_path does not exist: {content_path}")
        return path.read_text()

    if content:
        return content

    raise ValueError("Either 'content' or 'content_path' must be provided.")
