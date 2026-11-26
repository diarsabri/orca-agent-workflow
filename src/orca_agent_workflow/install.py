"""Install the workflow's project files; preview by default, never replace existing files."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from orca_agent_workflow import __version__, adoption, native, review_gate, task_scope

PACKAGE = Path(__file__).resolve().parent
TEMPLATE = PACKAGE / "template"
# Template paths drop leading dots so packaging keeps them; these names regain theirs.
DOTTED = {"agents", "claude", "opencode", "githooks", "gitignore", "gitattributes"}
OPTIONAL = {"opencode": "opencode/", "pre-push-hook": "githooks/"}
EXECUTABLE = {".agents/workflow.py", ".githooks/pre-push"}
RULE_FILES = {".gitignore", ".gitattributes"}  # existing files get the missing lines appended
RUNTIME = ".agents/runtime/orca_agent_workflow"
MERGE_FOLDER = ".tmp/orca-agent-workflow/merge"
KIT_DOCS = "https://github.com/diarsabri/orca-agent-workflow/blob/"


def destination(stored: str) -> str:
    first, _, rest = stored.partition("/")
    first = "." + first if first in DOTTED else first
    return f"{first}/{rest}" if rest else first


def template_files(optional: tuple[str, ...] = ()) -> dict[str, Path]:
    """Installed path -> template source, for the default files and requested groups."""
    unknown = set(optional) - set(OPTIONAL)
    if unknown:
        raise ValueError("Unknown optional files: " + ", ".join(sorted(unknown)))
    files = {}
    for source in sorted(TEMPLATE.rglob("*")):
        stored = source.relative_to(TEMPLATE).as_posix()
        if not source.is_file() or "__pycache__" in stored:
            continue
        group = next((g for g, prefix in OPTIONAL.items() if stored.startswith(prefix)), None)
        if group is None or group in optional:
            files[destination(stored)] = source
    return files


def runtime_files() -> dict[str, Path]:
    """The package itself, for `--vendor`: the launcher then prefers this copy."""
    return {
        f"{RUNTIME}/{source.relative_to(PACKAGE).as_posix()}": source
        for source in sorted(PACKAGE.rglob("*"))
        if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc"
    }


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path.name}")
    return value


def detect(root: Path) -> tuple[str, list[str]]:
    """Suggestions only: never run application commands or install dependencies."""
    if (root / "package.json").is_file():
        package = load(root / "package.json")
        manager = str(package.get("packageManager", "npm")).split("@")[0]
        if manager not in ("npm", "pnpm", "yarn", "bun"):
            manager = "npm"
        scripts = package.get("scripts", {})
        return "node", [f"{manager} run {key}" for key in ("check", "test") if key in scripts]
    if (root / "pyproject.toml").is_file() or list(root.glob("*.py")) or (root / "tests").is_dir():
        # Only suggest unittest when a real test module explicitly imports it.
        tests = list((root / "tests").glob("test*.py"))
        unittest_tests = tests and all(
            "import unittest" in p.read_text(encoding="utf-8") for p in tests
        )
        return "python", ["python3 -m unittest discover -s tests"] if unittest_tests else []
    return "other", []


def origin_repository(target: Path) -> str | None:
    if not (target / ".git").exists() or not shutil.which("git"):
        return None
    remote = subprocess.run(
        ["git", "-C", str(target), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([\w.-]+/[\w.-]+?)(?:\.git)?/?", remote
    )
    return match[1] if match else None


def render_config(target: Path, args: argparse.Namespace) -> bytes:
    """A new project's .agents/workflow.json; an existing one is never rewritten."""
    config = json.loads((TEMPLATE / "agents/workflow.json").read_text(encoding="utf-8"))
    stack, checks = detect(target) if target.exists() else ("other", [])
    name = args.name or target.name.replace("-", " ").replace("_", " ").title()
    repository = args.repository or origin_repository(target) or "local/" + re.sub(
        r"[^a-z0-9]+", "-", target.name.lower()
    ).strip("-")
    if not name.strip() or "\n" in name or "\r" in name:
        raise ValueError("Use a non-empty, single-line project name")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be owner/name")
    checks = args.check if args.check is not None else checks
    if any(not isinstance(c, str) or not c.strip() for c in checks):
        raise ValueError("Verification commands must be non-empty")
    agent = args.coordinator or (
        "claude" if shutil.which("claude") else "codex" if shutil.which("codex") else "claude"
    )
    model = next(
        p["model"]
        for p in config["roles"]["planner"]
        if p["agent"] == agent and p.get("enabled") is True
    )
    if not review_gate.exact_model(agent, model):
        raise ValueError("The default coordinator profile needs an exact model ID")
    config["runtime"]["version"] = __version__
    config["project"] = {
        "name": name,
        "repository": repository,
        "stack": args.stack or stack,
        "checks": checks,
        "coordinator": {"agent": agent, "model": model},
    }
    return (json.dumps(config, indent=2) + "\n").encode()


def proposed(relative: str, source: Path) -> bytes:
    data = source.read_bytes()
    if relative.endswith(".md"):
        # Kit docs as they were for this version, not as they are on main today.
        data = data.replace(
            (KIT_DOCS + "main/").encode(), f"{KIT_DOCS}v{__version__}/".encode()
        )
    return data


def append_missing_lines(original: bytes, proposed: bytes) -> bytes:
    """Keep an existing rules file; add only the proposed rule lines it lacks."""
    present = set(original.decode("utf-8").splitlines())
    lines = proposed.decode("utf-8").splitlines()
    missing = [s for s in lines if s and not s.startswith("#") and s not in present]
    if not missing:
        return original
    header = next((s for s in lines if s.startswith("#")), "# Orca agent workflow")
    data = original + (b"\n" if original and not original.endswith(b"\n") else b"")
    return data + ("\n" + header + "\n" + "\n".join(missing) + "\n").encode()


def safe_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Managed paths must be relative POSIX paths")
    if Path(name).is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("Managed paths cannot be absolute or contain traversal")
    path = root / name
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Refusing symlink: {current}")
        if current != path and current.exists() and not current.is_dir():
            raise ValueError(f"Managed parent is not a folder: {name}")
        current = current.parent
    if not path.resolve().is_relative_to(root):
        raise ValueError("Managed path escapes the project")
    return path


def plan(target: Path, args: argparse.Namespace, config: bytes | None = None) -> list[dict]:
    """Every managed file's action; `config` supplies a new project's workflow.json."""
    optional = tuple(
        g for g, on in (("opencode", args.opencode), ("pre-push-hook", args.pre_push_hook)) if on
    )
    files = template_files(optional)
    if args.vendor:
        files.update(runtime_files())
    operations = []
    for relative, source in files.items():
        path = safe_path(target, relative)
        if path.exists() and not path.is_file():
            raise ValueError(f"Expected a regular file: {relative}")
        original = path.read_bytes() if path.is_file() else None
        if relative == task_scope.CONFIG:
            if original is not None:
                pinned = task_scope.load_config(original)["runtime"].get("version")
                note = "unchanged" if pinned == __version__ else f"keep (pins {pinned})"
                operations.append({"path": relative, "action": note, "data": original})
                continue
            data = config if config is not None else render_config(target, args)
        else:
            data = proposed(relative, source)
        if original == data:
            action = "unchanged"
        elif original is None:
            action = "create"
        elif relative in RULE_FILES:
            data = append_missing_lines(original, data)
            action = "unchanged" if data == original else "append-rules"
        else:
            action = "merge"
        operations.append(
            {
                "path": relative,
                "action": action,
                "data": data,
                "original": original,
                "executable": relative in EXECUTABLE,
            }
        )
    return operations


def open_flags(path: Path, flags: int) -> int:
    # Windows has no O_NOFOLLOW and opens descriptors in text mode by default.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow and path.is_symlink():
        raise ValueError(f"Refusing to write through a symlink: {path}")
    return flags | nofollow | getattr(os, "O_BINARY", 0)


def write(path: Path, data: bytes, executable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, open_flags(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o755 if executable else 0o644
    )
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def apply(target: Path, operations: list[dict]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for operation in operations:
        path = safe_path(target, operation["path"])
        if operation["action"] == "create":
            write(path, operation["data"], operation["executable"])
        elif operation["action"] == "append-rules":
            if path.read_bytes() != operation["original"]:
                raise ValueError(f"File changed after preflight: {path}")
            extra = operation["data"][len(operation["original"]) :]
            descriptor = os.open(path, open_flags(path, os.O_WRONLY | os.O_APPEND))
            with os.fdopen(descriptor, "wb") as output:
                output.write(extra)
        elif operation["action"] == "merge":
            # The custom file stays; the candidate sits beside it for a semantic merge.
            candidate = safe_path(target, f"{MERGE_FOLDER}/{operation['path']}")
            if candidate.exists():
                candidate.unlink()
            write(candidate, operation["data"], False)


def main() -> int:
    parser = argparse.ArgumentParser(prog="orca-agent-workflow init", description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("."), help="Project folder")
    parser.add_argument("--apply", action="store_true", help="Write; without it, only preview")
    parser.add_argument("--name")
    parser.add_argument("--repository", help="GitHub owner/name (default: origin)")
    parser.add_argument("--stack", choices=("python", "node", "other"))
    parser.add_argument("--check", action="append", help="Verification command; repeatable")
    parser.add_argument("--coordinator", choices=("claude", "codex"))
    parser.add_argument("--opencode", action="store_true", help="Also install OpenCode commands")
    parser.add_argument(
        "--pre-push-hook", action="store_true", help="Also install the protected-branch hook"
    )
    parser.add_argument(
        "--vendor", action="store_true", help="Copy the runtime into .agents/runtime/"
    )
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise ValueError("Python 3.11 or newer is required")
        if args.target.is_symlink():
            raise ValueError("The target itself cannot be a symlink")
        target = args.target.expanduser().resolve()
        if target.exists() and not target.is_dir():
            raise ValueError("Target must be a directory")
        operations = plan(target, args)
        if args.apply:
            apply(target, operations)
        merges = [op["path"] for op in operations if op["action"] == "merge"]
        config = next(op["data"] for op in operations if op["path"] == task_scope.CONFIG)
        report = {
            "target": str(target),
            "version": __version__,
            "applied": args.apply,
            "project": task_scope.load_config(config)["project"],
            "current_revisions": adoption.revisions(target),
            "files": [{"path": op["path"], "action": op["action"]} for op in operations],
            "requires_merge": merges,
            "executable": [op["path"] for op in operations if op.get("executable")],
            "next": (
                "Review and commit the files, merge the listed ones by hand (candidates in "
                f"{MERGE_FOLDER}/), then run: python3 .agents/workflow.py check"
                if args.apply
                else "Nothing written. Re-run with --apply to install."
            ),
        }
        if suggestions := native.preview(target):
            report["native_verification"] = suggestions
        if args.apply and os.name == "nt":
            report["windows_executable_bits"] = (
                "Stage the files listed under executable with `git add --chmod=+x -- <paths>`."
            )
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"init: {exc}\n")
    return 0
