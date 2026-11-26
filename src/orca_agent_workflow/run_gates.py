#!/usr/bin/env python3
"""Run coordinator checks in a disposable local container from a trusted Git ref."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

from orca_agent_workflow import task_scope

DOCKER = "docker"  # an absolute path on Windows; see main()


def git(root: Path, *args: str) -> bytes:
    return task_scope.git_bytes(root, *args)


DEFAULT_DOCKERFILE = Path(__file__).resolve().parent / "gate.Dockerfile"


def default_dockerfile(root: Path, commit: str) -> bytes:
    """The runtime's own image: from the trusted ref when the runtime is in the checkout
    (the kit's source or a vendored copy), so a branch cannot supply its own image."""
    packaged = DEFAULT_DOCKERFILE.resolve()
    if packaged.is_relative_to(root.resolve()):
        relative = packaged.relative_to(root.resolve()).as_posix()
        return git(root, "show", f"{commit}:{relative}")
    return packaged.read_bytes()


def trusted_config(root: Path, ref: str) -> tuple[dict, dict[str, bytes]]:
    # Freeze ref to a full commit before reading config, Dockerfile or inputs.
    commit = git(root, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    config_data, workflow = task_scope.base_config(root, commit)
    config = dict(workflow.get("gates") or {})
    inputs = config.get("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("Unsupported gate configuration")
    files = {task_scope.CONFIG: config_data}
    if config.get("dockerfile") is None:
        # The pinned runtime's standard-library image; a project names its own to change it.
        if "Dockerfile" in inputs:
            raise ValueError("Name the project's Dockerfile in gates.dockerfile")
        config["dockerfile"] = "Dockerfile"
        files["Dockerfile"] = default_dockerfile(root, commit)
        paths = list(inputs)
    else:
        paths = [config["dockerfile"], *inputs]
    if len(paths) != len(set(paths)):
        raise ValueError("Gate build inputs must be unique")
    for path in paths:
        task_scope.relative(path)
        files[path] = git(root, "show", commit + ":" + path)
    timeout = config.get("timeout_seconds", 900)
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("Gate timeout must be an integer from 1 to 3600 seconds")
    if not re.fullmatch(r"[1-9][0-9]*[mg]", config.get("memory", "2g")):
        raise ValueError("Gate memory must be a positive m/g limit")
    return config, files


def default_ref(root: Path) -> str:
    """The remote's default branch: reviewed build inputs, never the branch under test."""
    try:
        ref = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").decode().strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "Could not find origin's default branch; pass --ref with the reviewed branch"
        ) from exc
    return ref


def index_modes(root: Path) -> dict[str, int]:
    """Executable bits as Git records them; Windows working trees do not carry them."""
    modes = {}
    for entry in git(root, "ls-files", "-s", "-z").split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            modes[name.decode()] = 0o755 if meta.startswith(b"100755") else 0o644
    return modes


def checkout_archive(root: Path) -> bytes:
    """Copy only selected regular checkout files; omit metadata and credentials."""
    names = git(root, "ls-files", "-z", "-c", "-o", "--exclude-standard").split(b"\0")
    modes = index_modes(root)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for raw in sorted(set(names)):
            if not raw:
                continue
            name = raw.decode()
            try:
                task_scope.relative(name)
            except ValueError:
                continue  # credential-shaped paths and local data roots are omitted
            path = root / name
            if not path.exists() and not path.is_symlink():
                continue
            if path.resolve() != path or not path.is_file():
                raise ValueError(f"Gate snapshots support regular files only: {name}")
            info = archive.gettarinfo(path, arcname=name)
            if name in modes:
                info.mode = modes[name]
            elif task_scope.WINDOWS:
                info.mode = 0o644  # untracked and no executable bit to read
            with path.open("rb") as data:
                archive.addfile(info, data)
    return stream.getvalue()


def ensure_local_docker() -> None:
    host = os.environ.get("DOCKER_HOST")
    if host and not host.startswith(("unix://", "npipe://")):
        raise ValueError("This starter runs gates only on a local Docker endpoint")
    result = subprocess.run(
        [DOCKER, "context", "inspect"], capture_output=True, text=True, check=True
    )
    contexts = json.loads(result.stdout)
    endpoint = contexts[0]["Endpoints"]["docker"]["Host"]
    if not endpoint.startswith(("unix://", "npipe://")):
        raise ValueError("This starter runs gates only on a local Docker endpoint")


def run_gate(tag: str, snapshot: bytes, command: str, config: dict) -> None:
    name = "orca-gate-" + uuid.uuid4().hex
    args = [
        DOCKER,
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--user",
        "10001:10001",
        "--memory",
        config.get("memory", "2g"),
        "--pids-limit",
        "256",
        "--cpus",
        "2",
        "--tmpfs",
        "/work:rw,nosuid,nodev,size=512m,uid=10001,gid=10001",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
        tag,
        "sh",
        "-c",
        'tar --no-same-owner -xf - -C /work && cd /work && exec sh -c "$1"',
        "sh",
        command,
    ]
    try:
        result = subprocess.run(args, input=snapshot, timeout=config.get("timeout_seconds", 900))
        if result.returncode:
            raise ValueError(f"Gate exited {result.returncode}: {command}")
    finally:
        # Exact unique owned name only; never prune containers or kill by process name.
        subprocess.run(
            [DOCKER, "rm", "--force", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default=os.environ.get("GATE_DEPS_REF"),
        help="Reviewed ref for gate build inputs (default: origin's default branch)",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("commands", nargs="*")
    args = parser.parse_args()
    try:
        root = Path(
            subprocess.check_output(
                [task_scope.git_executable(), "rev-parse", "--show-toplevel"], text=True
            ).strip()
        ).resolve()
        global DOCKER
        if task_scope.WINDOWS:
            # Never the checkout's own docker.exe, which bare-name lookup would find first.
            try:
                DOCKER = task_scope.host_executable("docker", root)
            except FileNotFoundError:
                raise ValueError("docker.exe was not found on PATH; install Docker Desktop")
        elif not shutil.which("docker"):
            raise ValueError("docker was not found on PATH; install and start Docker Desktop")
        ensure_local_docker()
        config, files = trusted_config(root, args.ref or default_ref(root))
        digest = hashlib.sha256()
        for path, data in sorted(files.items()):
            digest.update(path.encode() + b"\0" + data)
        tag = "orca-workflow-gates:" + digest.hexdigest()[:20]
        if subprocess.run(
            [DOCKER, "image", "inspect", tag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode:
            with tempfile.TemporaryDirectory(prefix="orca-gate-build-") as directory:
                context = Path(directory)
                for path, data in files.items():
                    destination = context / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
                print("Building trusted gate image; this build step uses network.", flush=True)
                subprocess.run(
                    [
                        DOCKER,
                        "build",
                        "-f",
                        str(context / config["dockerfile"]),
                        "-t",
                        tag,
                        str(context),
                    ],
                    check=True,
                    timeout=900,
                )
        snapshot = checkout_archive(root)
        if args.self_test:
            tests = [
                "python -c 'import sys; assert sys.flags.safe_path; print(\"safe import path: PASS\")'",
                'python -c \'import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(("1.1.1.1",53)); s.close(); assert r != 0; print("network denial: PASS")\'',
                'python -c \'import os,re; assert not [k for k in os.environ if re.search("token|secret|password|api_key|aws_|anthropic|openai",k,re.I)]; print("credential environment: PASS")\'',
            ]
            for command in tests:
                run_gate(tag, snapshot, command, config)
            print("Gate self-test: PASS", flush=True)
        if not args.commands and not args.self_test:
            raise ValueError("Provide at least one check or --self-test")
        for command in args.commands:
            print("Gate:", command, flush=True)
            run_gate(tag, snapshot, command, config)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"gate-sandbox: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
