#!/usr/bin/env python3
"""Append changelog entries to project info/CHANGELOG.md.

Usage:
    python update_changelog.py "Fixed HR voice stop command" "Updated HR guidance text"

This script adds a section for today's date if one does not already exist and inserts
bullet points under the date header.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

CHANGELOG_PATH = Path("project info") / "CHANGELOG.md"


def format_entry_lines(lines: list[str]) -> list[str]:
    return [f"- {line.strip()}" for line in lines if line.strip()]


def load_changelog(path: Path) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Changelog\n\n")
    return path.read_text(encoding="utf-8")


def save_changelog(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def insert_entries(content: str, date_header: str, entries: list[str]) -> str:
    lines = content.splitlines()
    insert_block = [date_header, "", *entries, ""]

    if date_header in lines:
        header_index = lines.index(date_header)
        insert_index = header_index + 1
        while insert_index < len(lines) and lines[insert_index].strip() == "":
            insert_index += 1
        for entry in entries:
            lines.insert(insert_index, entry)
            insert_index += 1
        return "\n".join(lines) + "\n"

    return "\n".join(insert_block + lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    summary_lines = sys.argv[1:]
    entries = format_entry_lines(summary_lines)
    if not entries:
        print("No valid changelog entries provided.")
        return 1

    date_header = f"## {datetime.date.today().isoformat()}"
    content = load_changelog(CHANGELOG_PATH)
    updated = insert_entries(content, date_header, entries)
    save_changelog(CHANGELOG_PATH, updated)
    print(f"Updated {CHANGELOG_PATH} with {len(entries)} entries under {date_header}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
