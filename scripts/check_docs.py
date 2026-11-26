#!/usr/bin/env python3
"""Verify local Markdown links without fetching external sites."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path) -> tuple[int, list[str]]:
    count, errors = 0, []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if any(part in (".git", ".tmp", ".venv", "node_modules") for part in relative.parts):
            continue
        if relative.as_posix().startswith("src/orca_agent_workflow/template/"):
            continue  # stored without leading dots; tests check its links once installed
        text = re.sub(r"^```.*?^```\s*$", "", path.read_text(encoding="utf-8"), flags=re.MULTILINE | re.DOTALL)
        for value in re.findall(r"\]\(([^)]+)\)", text):
            target = value.split("#")[0]
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            count += 1
            if not (path.parent / target).exists():
                errors.append(f"{path.relative_to(root)}: missing {target}")
    return count, errors


if __name__ == "__main__":
    count, errors = check(ROOT)
    for error in errors:
        print(error)
    print(f"Local links checked: {count}; errors: {len(errors)}")
    raise SystemExit(bool(errors))
