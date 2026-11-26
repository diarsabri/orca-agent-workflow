#!/usr/bin/env python3
"""Small publication guard; reports locations, never matched secret values."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "personal macOS path": re.compile("/" + r"Users/(?!example(?:/|\b))[^\s/]+"),
    "personal Linux path": re.compile("/" + r"home/(?!example(?:/|\b))[^\s/]+"),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "provider key": re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{30,}\b"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "captured Orca identity": re.compile(r"\b(?:ctx_|run_|term_|msg_)[0-9a-f-]{12,}\b"),
}


def candidates(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return [root / x.decode() for x in result.stdout.split(b"\0") if x]
    return [
        p
        for p in root.rglob("*")
        if p.is_file()
        and not any(
            part in (".git", ".tmp", ".venv", "__pycache__") for part in p.relative_to(root).parts
        )
    ]


def scan(root: Path) -> list[str]:
    errors = []
    for path in candidates(root):
        relative = path.relative_to(root)
        if path.is_symlink():
            errors.append(f"{relative}: publication symlinks need manual review")
            continue
        if not path.is_file():
            continue
        if any(
            part in (".tmp", ".aws", ".ssh") or part.startswith(".env") for part in relative.parts
        ):
            errors.append(f"{relative}: local evidence/credential-shaped file")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: binary file needs manual review")
            continue
        for label, pattern in PATTERNS.items():
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{relative}:{line}: {label}")
    return errors


if __name__ == "__main__":
    errors = scan(ROOT)
    for error in errors:
        print(error)
    print(f"Publication guard: {'FAIL' if errors else 'PASS'} ({len(errors)} findings)")
    raise SystemExit(bool(errors))
