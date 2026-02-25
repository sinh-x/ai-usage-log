#!/usr/bin/env python3
"""Bumps the ai-usage-log version across all files.

Usage:
    python tool/bump_version.py <version>
    python tool/bump_version.py patch|minor|major

Updates:
    - src/ai_usage_log/__init__.py  (source of truth)
    - pyproject.toml
    - flake.nix
    - CHANGELOG.md                  (adds new section from git log)
"""

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_root() -> Path:
    """Walk up from CWD until we find pyproject.toml + src/."""
    d = Path.cwd()
    while True:
        if (d / "pyproject.toml").exists() and (d / "src").exists():
            return d
        parent = d.parent
        if parent == d:
            print("Error: Could not find project root.")
            sys.exit(1)
        d = parent


def read_current_version(root: Path) -> str:
    init_file = root / "src" / "ai_usage_log" / "__init__.py"
    content = init_file.read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        print("Error: Could not read current version from __init__.py")
        sys.exit(1)
    return match.group(1)


def resolve_version(current: str, arg: str) -> str:
    # Strip pre-release suffix for bump calculations
    base = current.split("-")[0]
    parts = list(map(int, base.split(".")))
    if len(parts) != 3:
        print(f'Error: Current version "{current}" is not semver.')
        sys.exit(1)

    match arg:
        case "major":
            return f"{parts[0] + 1}.0.0"
        case "minor":
            return f"{parts[0]}.{parts[1] + 1}.0"
        case "patch":
            return f"{parts[0]}.{parts[1]}.{parts[2] + 1}"
        case _:
            if not re.match(r"^\d+\.\d+\.\d+$", arg):
                print(f'Error: "{arg}" is not a valid semver version or bump keyword.')
                sys.exit(1)
            return arg


def replace_in_file(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    if old not in content:
        print(f"  WARNING: Pattern not found in {path.name}")
        return
    path.write_text(content.replace(old, new, 1))
    print(f"  Updated {path.name}")


def update_changelog(root: Path, old_version: str, new_version: str) -> None:
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        print("  WARNING: CHANGELOG.md not found, skipping.")
        return

    # Get commits since last tag
    tag = f"v{old_version}"
    result = subprocess.run(
        ["git", "log", f"{tag}..HEAD", "--oneline"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # Categorize
    added: list[str] = []
    fixed: list[str] = []
    changed: list[str] = []

    for commit in commits:
        msg = re.sub(r"^[a-f0-9]+\s+", "", commit)
        display = re.sub(r"^(feat|fix|chore|refactor|docs|test|ci)(\([^)]*\))?:\s*", "", msg)
        capitalised = display[0].upper() + display[1:] if display else display

        if msg.startswith("feat"):
            added.append(capitalised)
        elif msg.startswith("fix"):
            fixed.append(capitalised)
        else:
            changed.append(capitalised)

    # Build new section
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"## [{new_version}] - {today}", ""]
    if added:
        lines.append("### Added")
        lines.extend(f"- {a}" for a in added)
        lines.append("")
    if fixed:
        lines.append("### Fixed")
        lines.extend(f"- {f}" for f in fixed)
        lines.append("")
    if changed:
        lines.append("### Changed")
        lines.extend(f"- {c}" for c in changed)
        lines.append("")
    if not commits:
        lines.append(f"_No conventional commits since {old_version}._")
        lines.append("")

    new_section = "\n".join(lines) + "\n"

    content = changelog.read_text()
    insert_point = content.find("\n## [")
    if insert_point >= 0:
        content = content[: insert_point + 1] + new_section + content[insert_point + 1 :]
    else:
        content += "\n" + new_section

    # Update link references
    link_line = f"[{new_version}]: https://github.com/sinh-x/ai-usage-log/compare/v{old_version}...v{new_version}"
    if f"[{new_version}]:" not in content:
        old_link = f"[{old_version}]:"
        link_pos = content.find(old_link)
        if link_pos >= 0:
            content = content[:link_pos] + link_line + "\n" + content[link_pos:]
        else:
            content += "\n" + link_line + "\n"

    changelog.write_text(content)
    print("  Updated CHANGELOG.md")


def main() -> None:
    if not sys.argv[1:] or sys.argv[1] in ("--help", "-h"):
        print("Usage: python tool/bump_version.py <version|patch|minor|major>")
        sys.exit(0)

    root = find_root()
    current = read_current_version(root)
    new = resolve_version(current, sys.argv[1])

    if new == current:
        print(f"Already at version {current} — nothing to do.")
        sys.exit(0)

    print(f"Bumping {current} → {new}\n")

    # 1. __init__.py (source of truth)
    replace_in_file(
        root / "src" / "ai_usage_log" / "__init__.py",
        f'__version__ = "{current}"',
        f'__version__ = "{new}"',
    )

    # 2. pyproject.toml
    replace_in_file(
        root / "pyproject.toml",
        f'version = "{current}"',
        f'version = "{new}"',
    )

    # 3. flake.nix (if version is present)
    flake = root / "flake.nix"
    if flake.exists():
        content = flake.read_text()
        if f'version = "{current}"' in content:
            replace_in_file(flake, f'version = "{current}"', f'version = "{new}"')

    # 4. CHANGELOG.md
    update_changelog(root, current, new)

    print(f"\nDone! Updated files to {new}.")
    print("\nNext steps:")
    print(f'  git add -A && git commit -m "chore: bump version to {new}"')
    print(f"  git tag v{new}")
    print("  git push origin main --tags")


if __name__ == "__main__":
    main()
