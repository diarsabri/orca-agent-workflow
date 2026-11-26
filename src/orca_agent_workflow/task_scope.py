#!/usr/bin/env python3
"""File-only task MCP broker, frozen review inputs, and owned-client lifecycle.

No worker shell, test runner, recursive delegation, or infrastructure interface.
The coordinator runs quality gates and separately approves operational work.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PureWindowsPath
from typing import Any

SELF = Path(__file__).resolve()
LIMIT = 2_000_000
PAGE = 8_000
# Fixed worker boundary. The approved per-task allowlist is the primary control;
# these categories should not need routine updates (see .agents/docs/task-permissions.md).
WORKFLOW_DIRS = {".agents", ".claude", ".codex", ".opencode", ".github", ".githooks"}
WORKFLOW_FILES = {".mcp.json", "opencode.json", "opencode.jsonc"}
WORKFLOW_PREFIXES = {
    ("scripts", "agents"),
    ("src", "orca_agent_workflow"),  # the runtime's own source, in the kit repository
    ("tests", "agents"),
    ("docs", "agents"),
    (".tmp", "agent-reviews"),
}
SENSITIVE_FILE = SELF.parent / "sensitive.json"
CONFIG = ".agents/workflow.json"
# Backstop only: the coordinator's exact per-task allowlist is the primary control.
CREDENTIAL_DIRS = {".git", ".aws", ".ssh"}
CREDENTIAL_FILES = {".npmrc", ".netrc", ".pgpass"}
CREDENTIAL_PREFIXES = (".env", "id_rsa", "id_ed25519", "id_ecdsa")
CREDENTIAL_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".bak",
    ".backup",
    ".dump",
    ".sql.gz",
    ".sql.bz2",
    ".sql.xz",
    ".sql.zst",
)
CREDENTIAL_ROOTS = {"data", "backups", "dumps"}
WINDOWS = os.name == "nt"
# Names Windows maps to devices in any folder, with or without an extension.
WINDOWS_DEVICES = {"con", "prn", "aux", "nul", "conin$", "conout$"} | {
    f"{kind}{n}" for kind in ("com", "lpt") for n in "123456789"
}
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def host_executable(name: str, root: Path | None = None, suffixes: tuple = (".exe",)) -> str:
    """Absolute program from absolute PATH entries outside the checkout. Windows would
    otherwise search the current directory first, which is often the branch under test."""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        folder = Path(entry.strip('"'))
        if not folder.is_absolute():
            continue
        for suffix in suffixes:
            candidate = folder / (name + suffix)
            if candidate.is_file():
                resolved = candidate.resolve()
                if root is not None and resolved.is_relative_to(root.resolve()):
                    continue
                return str(resolved)
    raise FileNotFoundError(f"{name} was not found on PATH outside the checkout")


def claude_executable(root: Path) -> str | None:
    if WINDOWS:
        return host_executable("claude", root, (".exe", ".cmd"))
    return shutil.which("claude")


def git_executable(root: Path | None = None) -> str:
    """Absolute Git outside the checkout; never resolved through the checkout or cwd."""
    if not WINDOWS:
        return "/usr/bin/git"
    try:
        return host_executable("git", root)
    except FileNotFoundError:
        raise FileNotFoundError("git.exe was not found on PATH; install Git for Windows")


def project_folder() -> Path:
    """The checkout, or the current folder of a project not yet under Git."""
    try:
        return project_root()
    except (ValueError, OSError):
        return Path.cwd().resolve()


def project_root(start: Path | None = None) -> Path:
    """The Git checkout the command runs in; the runtime no longer lives inside it."""
    folder = (start or Path.cwd()).resolve()
    output = subprocess.run(
        [git_executable(), "-C", str(folder), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if output.returncode:
        raise ValueError("Run this command inside the project's Git checkout")
    return Path(output.stdout.strip()).resolve()


def final_path(fd: int) -> str:
    """The real path Windows opened for this descriptor, after every link and junction."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get = kernel32.GetFinalPathNameByHandleW
    get.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    get.restype = wintypes.DWORD
    handle = msvcrt.get_osfhandle(fd)
    size = 512
    while True:
        buffer = ctypes.create_unicode_buffer(size)
        length = get(handle, buffer, size, 0)
        if not length:
            raise OSError(ctypes.get_last_error(), "Could not read the opened file's path")
        if length < size:
            break
        size = length + 1
    path = buffer.value
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    return path[4:] if path.startswith("\\\\?\\") else path


def windows_name_problem(segment: str) -> str | None:
    """Path components Windows would silently reinterpret or map to a device."""
    if ":" in segment:
        return "Drive-relative paths and alternate data streams are forbidden"
    if segment.endswith((".", " ")):
        return "Trailing dots and spaces are forbidden"
    if any(c in segment for c in '<>"|?*') or any(ord(c) < 32 for c in segment):
        return "Characters Windows reserves are forbidden"
    if segment.split(".", 1)[0].rstrip(" ").casefold() in WINDOWS_DEVICES:
        return "Windows device names are forbidden"
    return None


def is_credential(parts: tuple[str, ...]) -> bool:
    """Casefolded path components name a credential-bearing file or local data store."""
    return parts[0] in CREDENTIAL_ROOTS or any(
        s in CREDENTIAL_DIRS
        or s in CREDENTIAL_FILES
        or s.startswith(CREDENTIAL_PREFIXES)
        or s.endswith(CREDENTIAL_SUFFIXES)
        for s in parts
    )


def is_workflow_control(parts: tuple[str, ...]) -> bool:
    """Casefolded components name the workflow's own policy, tooling, specs or evidence."""
    name = parts[-1]
    return (
        parts[0] == "specs"
        or parts[:2] in WORKFLOW_PREFIXES
        or any(s in WORKFLOW_DIRS for s in parts)
        or name in WORKFLOW_FILES
        or (name.startswith(("agents", "claude")) and name.endswith(".md"))
    )


def sensitive_patterns(extra: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The runtime's default patterns plus the project's own from its trusted config."""
    data = json.loads(SENSITIVE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(p, str) and p for p in data.get("patterns", [None])
    ):
        raise ValueError("sensitive.json must hold a non-empty list of glob patterns")
    return [p.casefold() for p in [*data["patterns"], *extra]]


def load_config(data: bytes) -> dict[str, Any]:
    """Parse `.agents/workflow.json`: project, runtime pin, roles, gates and sensitive paths."""
    config = json.loads(data.decode("utf-8"))
    project = config.get("project") if isinstance(config, dict) else None
    if (
        not isinstance(config, dict)
        or type(config.get("version")) is not int
        or config["version"] != 1
        or not isinstance(project, dict)
        or not isinstance(project.get("repository"), str)
        or not isinstance(config.get("roles"), dict)
        or not isinstance(config.get("runtime"), dict)
    ):
        raise ValueError("Unsupported .agents/workflow.json; expected version 1")
    extra = config.get("sensitive_patterns", [])
    if not isinstance(extra, list) or not all(isinstance(p, str) and p for p in extra):
        raise ValueError("sensitive_patterns must be a list of glob patterns")
    return config


def roles_policy(config: dict[str, Any]) -> dict[str, Any]:
    """The roles view that profile checks and the review gate validate against."""
    return {
        "version": 2,
        "repository": config["project"]["repository"],
        "max_fix_rounds": config.get("max_fix_rounds", 2),
        "reviewer_provider_differs_from_planner": config.get(
            "reviewer_provider_differs_from_planner"
        ),
        "roles": config["roles"],
    }


def base_config(root: Path, ref: str) -> tuple[bytes, dict[str, Any]]:
    """The configuration as committed at a reviewed ref, never the working tree."""
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("The trusted policy ref must be a full commit SHA")
    try:
        data = git_bytes(root, "show", f"{ref}:{CONFIG}")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Cannot read {CONFIG} at the trusted revision {ref}. "
            "Verify that the revision is available locally and contains the reviewed policy. "
            "For default refs after adoption, check workflow.py status from the task checkout."
        ) from exc
    return data, load_config(data)


def is_sensitive(value: str, patterns: list[str]) -> bool:
    """Gate, build and deploy inputs: allowed only when the approved spec marks them."""
    path = value.casefold()
    name = path.rsplit("/", 1)[-1]
    # Patterns with a slash match the whole path; others match only the file name.
    return any(fnmatch.fnmatchcase(path if "/" in p else name, p) for p in patterns)


class ScopeEnded(ValueError):
    """The immutable task authority is no longer valid."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def atomic_json(path: Path, value: Any) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".scope-", delete=False, newline="\n"
    ) as output:
        target = Path(output.name)
        json.dump(value, output, indent=2)
        output.write("\n")
    target.replace(path)


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        [
            git_executable(root),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(root),
            *args,
        ],
        stderr=subprocess.DEVNULL,
    )


def git_ignored(root: Path, values: list[str]) -> set[str]:
    """Paths Git ignores; writes there would not appear in the coordinator's diff."""
    if not values:
        return set()
    result = subprocess.run(
        [
            git_executable(root),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(root),
            "check-ignore",
            "--stdin",
            "-z",
        ],
        input="\0".join(values).encode() + b"\0",
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError("Could not check ignored paths")
    return {v.decode() for v in result.stdout.split(b"\0") if v}


def relative(value: Any, write: bool = False) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Expected a relative POSIX file path")
    p = Path(value)
    if p.is_absolute() or any(s in ("", ".", "..") for s in value.split("/")):
        raise ValueError("Absolute paths, traversal, and ambiguous paths are forbidden")
    if WINDOWS:
        for segment in value.split("/"):
            problem = windows_name_problem(segment)
            if problem:
                raise ValueError(problem)
    parts = tuple(s.casefold() for s in value.split("/"))
    if is_credential(parts):
        raise ValueError("Credential paths are forbidden")
    if write and is_workflow_control(parts):
        raise ValueError(
            "Workers cannot edit workflow controls, approved specs, or review evidence"
        )
    if write and len(parts) == 1 and parts[0].endswith(".py"):
        raise ValueError("Workers cannot create root-level Python modules (module shadowing)")
    return value


def chunk(text: str, offset: Any = 0, limit: Any = PAGE) -> dict[str, Any]:
    if type(offset) is not int or offset < 0 or offset > len(text):
        raise ValueError("offset must be a valid character offset")
    if type(limit) is not int or not 1 <= limit <= 12_000:
        raise ValueError("limit must be between 1 and 12000 characters")
    end = min(len(text), offset + limit)
    while True:
        result = {
            "text": text[offset:end],
            "offset": offset,
            "next_offset": end if end < len(text) else None,
            "total_chars": len(text),
        }
        if len(json.dumps(result, ensure_ascii=False).encode()) <= 16_000:
            return result
        end = offset + max(1, (end - offset) // 2)


def orca_executable() -> str:
    """The Orca CLI. On Windows only an absolute native executable: cmd.exe re-parses a
    batch launcher's arguments, so worker-supplied question or report text could run."""
    executable = os.environ.get("ORCA_CLI") or shutil.which("orca") or "orca"
    if WINDOWS:
        path = PureWindowsPath(executable)
        # Compare the whole name: older Pythons report no suffix for "orca.cmd.", and
        # Windows drops the trailing dot and runs the batch file.
        if not path.is_absolute() or path.name.casefold() != "orca.exe":
            raise ValueError(f"{executable} is not a native orca.exe; put it first on PATH")
    return executable


def orca(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        [orca_executable(), "orchestration", *args, "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        data = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError("Orca returned no valid receipt") from exc
    if not isinstance(data, dict):
        raise ValueError("Orca returned an invalid receipt shape")
    if result.returncode or data.get("ok") is not True:
        raise ValueError("Orca operation failed: " + str(data.get("error", result.stderr[:300])))
    if not isinstance(data.get("result"), dict):
        raise ValueError("Orca returned an invalid result shape")
    return data["result"]


class Scope:
    def __init__(
        self, manifest: Path, bundle: Path | None = None, probe_folder: str | None = None
    ):
        self.manifest = manifest.resolve(strict=True)
        self.bundle = bundle.resolve(strict=True) if bundle else None
        self.sha = digest(self.manifest)
        self.data = json.loads(self.manifest.read_text(encoding="utf-8"))
        d = self.data
        fields = {
            "version",
            "root",
            "head",
            "role",
            "approval_reference",
            "expires_at",
            "read",
            "write",
            "sensitive",
            "commands",
            "runtime_read",
            "infrastructure",
            "policy_base",
            "sensitive_extra",
        }
        if (
            not isinstance(d, dict)
            or set(d) != fields
            or type(d["version"]) is not int
            or d["version"] != 3
        ):
            raise ValueError("Unsupported manifest fields/version")
        if not isinstance(d["policy_base"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", d["policy_base"]
        ):
            raise ValueError("policy_base must be the full commit whose policy is trusted")
        if not isinstance(d["sensitive_extra"], list) or not all(
            isinstance(v, str) and v for v in d["sensitive_extra"]
        ):
            raise ValueError("sensitive_extra must list the project's sensitive patterns")
        if (
            d["role"] not in ("implementer", "reviewer")
            or not isinstance(d["approval_reference"], str)
            or not d["approval_reference"].strip()
        ):
            raise ValueError("Role and approval reference are required")
        if (
            type(d["expires_at"]) not in (float, int)
            or not time.time() < d["expires_at"] <= time.time() + 8 * 3600
        ):
            raise ValueError("Task grants must expire within eight hours")
        if d["commands"] != {} or d["runtime_read"] != []:
            raise ValueError("Worker execution is unsupported; the coordinator runs quality gates")
        if d["infrastructure"] != []:
            raise ValueError("Infrastructure requires a separate task-specific user grant")
        self.root = Path(d["root"]).resolve(strict=True)
        if not self.root.is_dir() or str(self.root) != d["root"]:
            raise ValueError("root must be a canonical directory")
        if not isinstance(d["head"], str) or not re.fullmatch(r"[a-f0-9]{40}", d["head"]):
            raise ValueError("A full Git head is required")
        self.read = self.paths(d["read"], existing=True)
        self.write = self.paths(d["write"], existing=False)
        if d["role"] == "reviewer" and self.write:
            raise ValueError("Reviewer grants cannot include writes")
        # Ignored paths are invisible to diff inspection. Reviewers may read frozen
        # evidence under .tmp/agent-reviews/; the broker probe uses one synthetic folder.
        allowed_ignored = (".tmp/agent-reviews/",) if d["role"] == "reviewer" else ()
        if probe_folder:
            allowed_ignored += (probe_folder.rstrip("/") + "/",)
        self.allowed_ignored = allowed_ignored
        hidden = git_ignored(self.root, sorted(self.read | self.write))
        if any(not v.startswith(allowed_ignored) for v in hidden):
            raise ValueError("Git-ignored paths are forbidden; the diff cannot show them")
        if (
            not isinstance(d["sensitive"], list)
            or not all(isinstance(v, str) for v in d["sensitive"])
            or not set(d["sensitive"]) <= self.write
        ):
            raise ValueError("sensitive must list paths that are also approved writes")
        self.sensitive = set(d["sensitive"])
        patterns = sensitive_patterns(d["sensitive_extra"])
        unmarked = [v for v in self.write if is_sensitive(v, patterns) and v not in self.sensitive]
        if unmarked:
            raise ValueError(
                "Sensitive path not marked in the approved spec: " + ", ".join(sorted(unmarked))
            )
        self.inputs = json.loads((self.bundle / "inputs.json").read_text(encoding="utf-8")) if self.bundle else {}
        self.mail: dict[str, dict[str, Any]] = {}
        self.live()

    def paths(self, values: Any, existing: bool) -> set[str]:
        if (
            not isinstance(values, list)
            or not all(isinstance(v, str) for v in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("Paths must be a list of unique strings")
        result = set()
        for value in values:
            relative(value, write=not existing)
            p = self.root / value
            if p.resolve() != p or not p.parent.is_dir():
                raise ValueError("Path has a symlink or missing parent")
            if p.exists():
                info = p.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("Only individual regular files with one link are supported")
            elif existing:
                raise ValueError("A declared input does not exist")
            result.add(value)
        return result

    def live(self) -> None:
        if digest(self.manifest) != self.sha or self.manifest.with_suffix(".revoked").exists():
            raise ScopeEnded("Task authority changed or was revoked")
        if time.time() >= self.data["expires_at"]:
            raise ScopeEnded("Task grant expired")
        try:
            current = git_bytes(self.root, "rev-parse", "HEAD").decode().strip()
            if current != self.data["head"]:
                raise ScopeEnded("Checkout head changed")
            if self.data["role"] == "reviewer":
                git_bytes(
                    self.root, "diff", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--"
                )
        except subprocess.CalledProcessError as exc:
            raise ScopeEnded("Reviewer requires a clean tracked checkout") from exc
        # A granted .gitignore edit must not hide a later write from the diff.
        if self.write and any(
            not v.startswith(self.allowed_ignored)
            for v in git_ignored(self.root, sorted(self.write))
        ):
            raise ScopeEnded("An approved write path became Git-ignored")

    def open_file(self, value: str, write: bool = False) -> int:
        self.live()
        relative(value, write=write)
        if value not in (self.write if write else self.read | self.write):
            raise PermissionError("Path is outside the approved task scope")
        if WINDOWS:
            return self.open_file_windows(value, write)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parts = value.split("/")
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            flags = (os.O_WRONLY if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
            try:
                target = os.open(parts[-1], flags, dir_fd=fd)
            except FileNotFoundError:
                if not write:
                    raise
                target = os.open(parts[-1], flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            info = os.fstat(target)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(target)
                raise PermissionError("Special file, symlink, or hardlink refused")
            return target
        finally:
            os.close(fd)

    def open_file_windows(self, value: str, write: bool) -> int:
        """Windows has no dir_fd or O_NOFOLLOW. Refuse reparse points on the way in,
        then trust only the path Windows reports for the handle actually opened, so a
        swap between the checks and the open cannot redirect the read or write."""
        expected = self.root.joinpath(*value.split("/"))
        current = self.root
        for part in value.split("/"):
            current = current / part
            try:
                info = os.lstat(current)
            except FileNotFoundError:
                if not write or current != expected:
                    raise
                break
            if info.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise PermissionError("Special file, symlink, or hardlink refused")
        flags = (os.O_WRONLY if write else os.O_RDONLY) | os.O_BINARY | os.O_NOINHERIT
        try:
            target = os.open(expected, flags)
        except FileNotFoundError:
            if not write:
                raise
            target = os.open(expected, flags | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            opened = final_path(target)
            info = os.fstat(target)
        except OSError:
            os.close(target)
            raise
        if os.path.normcase(opened) != os.path.normcase(str(expected)):
            os.close(target)
            raise PermissionError("Special file, symlink, or hardlink refused")
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(target)
            raise PermissionError("Special file, symlink, or hardlink refused")
        return target

    def read_bytes(self, value: str) -> bytes:
        relative(value)
        if value not in self.read | self.write:
            raise PermissionError("Path is outside the approved task scope")
        if self.data["role"] == "reviewer":
            if not self.bundle or value not in self.inputs:
                raise ValueError("Reviewer requires frozen inputs")
            item = self.inputs[value]
            name = item["file"]
            if not re.fullmatch(r"[0-9]{4}\.bin", name):
                raise ValueError("Invalid frozen input name")
            data = (self.bundle / "inputs" / name).read_bytes()
            if sha(data) != item["sha256"]:
                raise ScopeEnded("Frozen review input changed")
        else:
            with os.fdopen(self.open_file(value), "rb") as f:
                data = f.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Input exceeds 2 MB; provide a smaller approved artifact")
        return data

    def own_dispatch(self, dispatch: Any, task: Any = None) -> dict[str, Any]:
        handle = os.environ.get("ORCA_TERMINAL_HANDLE")
        if (
            not handle
            or not isinstance(dispatch, str)
            or not re.fullmatch(r"ctx_[a-z0-9]+", dispatch)
        ):
            raise ValueError("An Orca-owned terminal and valid dispatch are required")
        state = orca("worker-show", "--dispatch", dispatch)
        workspace = state.get("workspace")
        if (
            state.get("terminal") != handle
            or not isinstance(workspace, str)
            or not workspace.endswith("::" + str(self.root))
        ):
            raise PermissionError("Dispatch does not belong to this task terminal/workspace")
        if task is not None and state.get("taskId") != task:
            raise PermissionError("Task does not match the dispatch")
        return state

    def call(self, name: Any, arguments: Any) -> Any:
        self.live()
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("Tool name and argument object are required")
        keys = set(arguments)
        if name == "read_file" and {"path"} <= keys <= {"path", "offset", "limit"}:
            text = self.read_bytes(arguments["path"]).decode("utf-8")
            return chunk(text, arguments.get("offset", 0), arguments.get("limit", PAGE))
        if name == "write_file" and keys == {"path", "content"}:
            if not isinstance(arguments["content"], str):
                raise ValueError("content must be UTF-8 text")
            data = arguments["content"].encode()
            if len(data) > LIMIT:
                raise ValueError("Write exceeds 2 MB")
            with os.fdopen(self.open_file(arguments["path"], True), "wb") as f:
                f.truncate(0)
                f.write(data)
            return {"written": arguments["path"]}
        if name == "request_scope" and keys == {"question"}:
            if not os.environ.get("ORCA_TERMINAL_HANDLE") or not isinstance(
                arguments["question"], str
            ):
                raise ValueError("Scope questions require an Orca terminal and text")
            return orca(
                "ask",
                "--from",
                os.environ["ORCA_TERMINAL_HANDLE"],
                "--question",
                arguments["question"],
            )
        if name == "mailbox" and {"dispatch_id"} <= keys <= {
            "dispatch_id",
            "message_id",
            "offset",
            "limit",
        }:
            self.own_dispatch(arguments["dispatch_id"])
            message_id = arguments.get("message_id")
            if message_id is None:
                result = orca("check", "--terminal", os.environ["ORCA_TERMINAL_HANDLE"])
                messages = result.get("messages", [])
                if not isinstance(messages, list):
                    raise ValueError("Orca returned an invalid mailbox shape")
                for message in messages:
                    if isinstance(message, dict) and isinstance(message.get("id"), str):
                        self.mail[message["id"]] = message
                return {
                    "messages": [
                        {
                            "id": m["id"],
                            "type": m.get("type"),
                            "subject": m.get("subject"),
                            "body_chars": len(str(m.get("body", ""))),
                        }
                        for m in self.mail.values()
                    ]
                }
            if not isinstance(message_id, str) or message_id not in self.mail:
                raise PermissionError("Message is not in this dispatch mailbox cache")
            return chunk(
                str(self.mail[message_id].get("body", "")),
                arguments.get("offset", 0),
                arguments.get("limit", PAGE),
            )
        if name == "report" and keys == {"outcome", "body", "task_id", "dispatch_id"}:
            if arguments["outcome"] not in ("succeeded", "failed") or not all(
                isinstance(arguments[k], str) for k in ("body", "task_id", "dispatch_id")
            ):
                raise ValueError("Invalid report")
            self.own_dispatch(arguments["dispatch_id"], arguments["task_id"])
            # Revoke once a send is attempted, even if its receipt is malformed,
            # so a worker cannot retry into a duplicate report.
            try:
                return orca(
                    "send",
                    "--type",
                    "worker_done",
                    "--subject",
                    "Scoped worker report",
                    "--outcome",
                    arguments["outcome"],
                    "--body",
                    arguments["body"],
                    "--task-id",
                    arguments["task_id"],
                    "--dispatch-id",
                    arguments["dispatch_id"],
                )
            finally:
                self.manifest.with_suffix(".revoked").touch()
        raise PermissionError("Tool or argument shape is outside the approved interface")


def tools(scope: Scope) -> list[dict[str, Any]]:
    def tool(
        name: str, description: str, fields: dict[str, Any], required: list[str] | None = None
    ) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": fields,
                "required": list(fields) if required is None else required,
                "additionalProperties": False,
            },
        }

    string = {"type": "string"}
    pages = {
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 12000},
    }
    result = [
        tool(
            "read_file",
            "Read an approved file in bounded pages; follow next_offset until null.",
            {"path": string, **pages},
            ["path"],
        ),
        tool(
            "request_scope",
            "Ask the coordinator. End your turn; on wake use mailbox. This grants no access.",
            {"question": string},
        ),
        tool(
            "mailbox",
            "Read only your dispatch mail on Orca wake. Fetch IDs, then page bodies by message_id; never poll.",
            {"dispatch_id": string, "message_id": string, **pages},
            ["dispatch_id"],
        ),
        tool(
            "report",
            "Complete this exact task/dispatch through Orca; revokes access and closes the scoped client.",
            {
                "outcome": {"enum": ["succeeded", "failed"]},
                "body": string,
                "task_id": string,
                "dispatch_id": string,
            },
        ),
    ]
    if scope.write:
        result.append(
            tool(
                "write_file",
                "Write one approved UTF-8 file; no execution or directory operations.",
                {"path": string, "content": string},
            )
        )
    return result


def serve(scope: Scope) -> None:
    def error(code: int, message: str, request_id: Any = None) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    while True:
        raw = sys.stdin.buffer.readline(LIMIT + 1)
        if not raw:
            return
        if len(raw) > LIMIT:
            while raw and not raw.endswith(b"\n"):
                raw = sys.stdin.buffer.readline(LIMIT + 1)
            print(json.dumps(error(-32600, "Request exceeds 2 MB")), flush=True)
            continue
        try:
            request = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            print(json.dumps(error(-32700, "Invalid JSON")), flush=True)
            continue
        if (
            not isinstance(request, dict)
            or request.get("jsonrpc") != "2.0"
            or not isinstance(request.get("method"), str)
        ):
            print(json.dumps(error(-32600, "Invalid request")), flush=True)
            continue
        if "id" not in request:
            continue
        request_id = request["id"]
        if request_id is not None and type(request_id) not in (str, int):
            print(json.dumps(error(-32600, "Invalid request ID")), flush=True)
            continue
        response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        try:
            scope.live()
            method, params = request["method"], request.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            if method == "initialize":
                version = params.get("protocolVersion")
                if not isinstance(version, str):
                    raise ValueError("protocolVersion must be text")
                result = {
                    "protocolVersion": version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "orca-task-scope", "version": "2.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": tools(scope)}
            elif method == "tools/call":
                try:
                    output = scope.call(params.get("name"), params.get("arguments", {}))
                    result = {
                        "content": [
                            {"type": "text", "text": json.dumps(output, ensure_ascii=False)}
                        ]
                    }
                except ScopeEnded:
                    raise
                except Exception as exc:  # one bad request must not end the broker loop
                    result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
            elif method == "ping":
                result = {}
            else:
                raise ValueError("Unsupported MCP method")
            response["result"] = result
        except ScopeEnded as exc:
            scope.manifest.with_suffix(".revoked").touch()
            response = error(-32602, str(exc), request_id)
        except Exception as exc:  # one bad request must not end the broker loop
            response = error(-32602, str(exc), request_id)
        print(json.dumps(response), flush=True)


def require_supported_harness(harness: str | None) -> None:
    if harness != "claude":
        raise ValueError(
            "Only scoped Claude workers are enabled; Codex native capability scope remains unverified"
        )


def enabled_profile(policy: dict[str, Any], role: str, agent: str, model: str | None) -> bool:
    """An exact, enabled role profile from the trusted policy; no aliases or fallbacks."""
    profiles = policy.get("roles", {}).get(role) if policy.get("version") == 2 else None
    return isinstance(profiles, list) and any(
        isinstance(p, dict)
        and p.get("agent") == agent
        and p.get("model") == model
        and p.get("enabled") is True
        for p in profiles
    )


def validate_model(role: str, model: str | None, policy: dict[str, Any]) -> None:
    if (
        not model
        or not re.fullmatch(r"claude-[a-z0-9][a-z0-9._-]*", model)
        or not enabled_profile(policy, role, "claude", model)
    ):
        raise ValueError(
            "Model is not an enabled exact role profile; aliases/fallbacks are forbidden"
        )


def prepare(
    scope: Scope, bundle: Path, model: str | None, policy_path: Path | None = None
) -> None:
    if policy_path is None:
        # The committed policy at the manifest's trusted base, never the working tree.
        _, config = base_config(scope.root, scope.data["policy_base"])
    else:
        config = load_config(policy_path.read_bytes())
    policy = roles_policy(config)
    validate_model(scope.data["role"], model, policy)
    bundle = bundle.resolve()
    if bundle.exists() or bundle.is_relative_to(scope.root):
        raise ValueError("Bundle must be a new coordinator-owned directory outside the checkout")
    binaries = {}
    claude = claude_executable(scope.root)
    for name, candidate in [("claude", claude), ("python", sys.executable)]:
        if not candidate:
            raise ValueError("Required client executable is unavailable")
        path = Path(candidate).resolve(strict=True)
        binaries[name] = {"path": str(path), "sha256": digest(path)}
    bundle.mkdir(parents=True, mode=0o700)
    (bundle / "work").mkdir(mode=0o700)
    (bundle / "inputs").mkdir(mode=0o700)
    shutil.copyfile(SELF, bundle / "task_scope.py")
    shutil.copyfile(scope.manifest, bundle / "manifest.json")
    atomic_json(bundle / "orchestration.json", policy)
    shutil.copyfile(SENSITIVE_FILE, bundle / "sensitive.json")
    index = {}
    if scope.data["role"] == "reviewer":
        for i, path in enumerate(sorted(scope.read)):
            if path.startswith(".tmp/"):
                with os.fdopen(scope.open_file(path), "rb") as f:
                    data = f.read(LIMIT + 1)
            else:
                data = git_bytes(scope.root, "cat-file", "blob", scope.data["head"] + ":" + path)
            if len(data) > LIMIT:
                raise ValueError("Review input exceeds 2 MB")
            name = f"{i:04}.bin"
            (bundle / "inputs" / name).write_bytes(data)
            index[path] = {"file": name, "sha256": sha(data), "head": scope.data["head"]}
    scope.live()
    atomic_json(bundle / "inputs.json", index)
    atomic_json(bundle / "executables.json", binaries)
    atomic_json(
        bundle / "mcp.json",
        {
            "mcpServers": {
                "task": {
                    "command": binaries["python"]["path"],
                    "args": [
                        "-I",
                        str(bundle / "task_scope.py"),
                        "serve",
                        "--manifest",
                        str(bundle / "manifest.json"),
                        "--bundle",
                        str(bundle),
                    ],
                }
            }
        },
    )
    atomic_json(
        bundle / "settings.json",
        {
            "autoMemoryEnabled": False,
            "claudeMdExcludes": ["/**"],
            "pluginConfigs": {
                "cc-plugin-agents-md@builtin": {"options": {"instructionFiles": "managed-only"}}
            },
        },
    )
    argv = [
        binaries["claude"]["path"],
        "--restricted",
        "--disable-slash-commands",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(bundle / "mcp.json"),
        "--setting-sources",
        "",
        "--permission-mode",
        "manual",
        "--settings",
        str(bundle / "settings.json"),
        "--model",
        model,
        "--allowedTools",
    ]
    argv += ["mcp__task__" + t["name"] for t in tools(scope)]
    atomic_json(bundle / "claude-argv.json", argv)


def bundle_files(bundle: Path) -> set[str]:
    files = {
        "manifest.json",
        "task_scope.py",
        "orchestration.json",
        "sensitive.json",
        "inputs.json",
        "executables.json",
        "mcp.json",
        "settings.json",
        "claude-argv.json",
    }
    inputs = json.loads((bundle / "inputs.json").read_text(encoding="utf-8"))
    for item in inputs.values():
        name = item["file"]
        if not re.fullmatch(r"[0-9]{4}\.bin", name):
            raise ValueError("Invalid frozen input name")
        files.add("inputs/" + name)
    return files


def verify_bundle(bundle: Path, scope: Scope) -> list[str]:
    receipt = json.loads((bundle / "probe.json").read_text(encoding="utf-8"))
    hashes = receipt.get("bundle_hashes")
    if receipt.get("passed") is not True or receipt.get("manifest_sha256") != scope.sha:
        raise ValueError("Missing or stale probe receipt")
    if not isinstance(hashes, dict) or set(hashes) != bundle_files(bundle):
        raise ValueError("Incomplete launch/input hash coverage")
    for name, expected in hashes.items():
        if digest(bundle / name) != expected:
            raise ValueError("Bundle changed after probing")
    if SELF != bundle / "task_scope.py":
        raise ValueError("Launch must use the frozen adapter")
    executables = json.loads((bundle / "executables.json").read_text(encoding="utf-8"))
    for item in executables.values():
        path = Path(item["path"])
        if path.resolve(strict=True) != path or digest(path) != item["sha256"]:
            raise ValueError("Pinned client/interpreter executable changed")
    argv = json.loads((bundle / "claude-argv.json").read_text(encoding="utf-8"))
    if argv[0] != executables["claude"]["path"]:
        raise ValueError("Client argv does not use the pinned executable")
    return argv


def probe(scope: Scope, bundle: Path) -> dict[str, Any]:
    """Test the actual file broker using only fresh synthetic checkout fixtures."""
    scope.live()
    scratch = scope.root / ".tmp"
    if scratch.resolve() != scratch:
        raise ValueError("Probe scratch path must not be a symlink")
    scratch.mkdir(exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix="scope-probe-") as tmp:
        folder = Path(tmp)
        allowed = folder / "read.txt"
        writable = folder / "write.txt"
        denied = folder / "denied.txt"
        allowed.write_text("approved input", encoding="utf-8", newline="\n")
        writable.write_text("before", encoding="utf-8", newline="\n")
        denied.write_text("synthetic private", encoding="utf-8", newline="\n")
        names = [p.relative_to(scope.root).as_posix() for p in (allowed, writable, denied)]
        data = {
            **scope.data,
            "role": "implementer",
            "read": [names[0]],
            "write": [names[1]],
            "sensitive": [],
        }
        manifest = folder / "probe.json"
        atomic_json(manifest, data)
        fixture = Scope(manifest, probe_folder=folder.relative_to(scope.root).as_posix())
        if fixture.call("read_file", {"path": names[0]})["text"] != "approved input":
            raise ValueError("Approved read failed")
        checks.append("approved_read")
        fixture.call("write_file", {"path": names[1], "content": "after"})
        if writable.read_text(encoding="utf-8") != "after":
            raise ValueError("Approved write failed")
        checks.append("approved_write")
        for check, tool, args in [
            ("denied_unlisted_sibling_read", "read_file", {"path": names[2]}),
            ("denied_read_only_write", "write_file", {"path": names[0], "content": "bad"}),
            ("denied_traversal", "read_file", {"path": "../outside"}),
            ("denied_execution", "run_check", {"id": "unapproved"}),
        ]:
            try:
                fixture.call(tool, args)
            except (ValueError, PermissionError):
                checks.append(check)
            else:
                raise ValueError("Broker allowed an unapproved operation")
        if allowed.read_text(encoding="utf-8") != "approved input" or denied.read_text(encoding="utf-8") != "synthetic private":
            raise ValueError("Negative probe changed a protected fixture")
    scope.live()
    return {
        "passed": True,
        "manifest_sha256": scope.sha,
        "checked_at": time.time(),
        "checks": checks,
        "bundle_hashes": {name: digest(bundle / name) for name in bundle_files(bundle)},
    }


def controller_status(bundle: Path) -> dict[str, Any]:
    path = bundle / "controller.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"state": "not_started"}


def kill_on_close_job(process: subprocess.Popen) -> Any:
    """Windows: tie the client and the broker it starts to a job that dies with this
    supervisor. Cleanup only; a stray broker still refuses calls once revoked."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", Basic),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "Could not create a job object")
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise OSError(ctypes.get_last_error(), "Could not configure the job object")
    if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
        raise OSError(ctypes.get_last_error(), "Could not assign the client to its job")
    return job


def close_job(job: Any) -> None:
    import ctypes

    ctypes.WinDLL("kernel32").CloseHandle(job)


def supervise(bundle: Path, scope: Scope, argv: list[str]) -> int:
    """Own precisely one newly created client; never adopt or signal other PIDs."""
    scope.live()
    process = subprocess.Popen(argv, cwd=bundle / "work")
    job = None
    if WINDOWS:
        try:
            job = kill_on_close_job(process)
        except OSError:
            process.kill()
            process.wait()
            raise
    state = {
        "state": "running",
        "pid": process.pid,
        "bundle": str(bundle),
        "manifest_sha256": scope.sha,
        "head": scope.data["head"],
        "terminal": os.environ.get("ORCA_TERMINAL_HANDLE"),
        "started_at": time.time(),
    }
    atomic_json(bundle / "controller.json", state)
    reason = "client_exit"
    try:
        while process.poll() is None:
            marker = scope.manifest.with_suffix(".revoked")
            if (
                marker.exists()
                or digest(scope.manifest) != scope.sha
                or time.time() >= scope.data["expires_at"]
            ):
                reason = "grant_ended"
                marker.touch()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        result = process.wait()
        if job is not None:
            close_job(job)  # ends any broker child the client left behind
        scope.manifest.with_suffix(".revoked").touch()
        atomic_json(
            bundle / "controller.json",
            {
                **state,
                "state": "exited",
                "returncode": result,
                "ended_at": time.time(),
                "reason": reason,
            },
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["serve", "validate", "prepare", "probe", "launch", "revoke", "status"]
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--harness", choices=["claude", "codex"])
    args = parser.parse_args()
    bundle = args.bundle.resolve() if args.bundle else None
    if args.action in ("revoke", "status"):
        if not bundle or not (bundle / "manifest.json").is_file():
            parser.error("revoke/status requires a prepared --bundle")
        if args.action == "revoke":
            (bundle / "manifest.revoked").touch()
        print(json.dumps(controller_status(bundle)))
        return
    if not args.manifest:
        parser.error("--manifest is required")
    if args.action in ("prepare", "launch"):
        require_supported_harness(args.harness)
    scope = Scope(args.manifest, bundle if args.action in ("serve", "probe", "launch") else None)
    if args.action == "serve":
        serve(scope)
    elif args.action == "validate":
        print(json.dumps({"valid": True, "manifest_sha256": scope.sha}))
    elif args.action == "prepare":
        if not bundle:
            parser.error("prepare requires --bundle")
        prepare(scope, bundle, args.model, args.policy)
        print(json.dumps({"bundle": str(bundle), "status": "prepared_not_probed"}))
    elif args.action == "probe":
        if not bundle:
            parser.error("probe requires --bundle")
        receipt = probe(scope, bundle)
        atomic_json(bundle / "probe.json", receipt)
        print(json.dumps(receipt))
    elif args.action == "launch":
        if not bundle or scope.manifest != bundle / "manifest.json":
            parser.error("launch requires the frozen bundle manifest")
        argv = verify_bundle(bundle, scope)
        raise SystemExit(supervise(bundle, scope, argv))


if __name__ == "__main__":
    main()
