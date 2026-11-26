#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Read local Claude/Codex JSONL history without a model call or session mutation."""

import argparse
from collections import deque
import json
import os
from pathlib import Path
import re
import sys


def records(path, limit=None):
    """Read a fixed prefix: a live writer cannot extend this read indefinitely."""
    remaining = path.stat().st_size if limit is None else limit
    with path.open("rb") as stream:
        while remaining > 0:
            line = stream.readline(remaining)
            remaining -= len(line)
            if not line:
                break
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # A writer may not have completed its final JSONL record yet.
                if remaining == 0 and not line.endswith(b"\n"):
                    break
                raise ValueError("Malformed JSONL record; refusing a silent partial recovery")
            if isinstance(item, dict):
                yield item


def identity(path, agent):
    for item in records(path):
        if agent == "codex" and item.get("type") == "session_meta":
            p = item.get("payload", {})
            return {
                "id": p.get("id"),
                "cwd": p.get("cwd"),
                "subagent": isinstance(p.get("source"), dict),
            }
        if agent == "claude" and item.get("cwd") and item.get("sessionId"):
            return {
                "id": item["sessionId"],
                "cwd": item["cwd"],
                "subagent": bool(item.get("isSidechain")),
            }
    raise ValueError("No supported session identity/cwd in transcript")


def same_cwd(actual, expected):
    # Do not resolve deleted legacy paths into unrelated projects by name.
    return bool(actual) and os.path.normpath(actual) == os.path.normpath(str(expected))


def text_blocks(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            block.get("text", "")
            for block in value
            if isinstance(block, dict)
            and block.get("type") in {"text", "input_text", "output_text"}
        )
    return ""


def events(path, agent, size):
    if agent == "codex":
        for item in records(path, size):
            p = item.get("payload", {})
            if item.get("type") == "response_item":
                if p.get("type") == "message" and p.get("role") in {"user", "assistant"}:
                    if p.get("channel") in {"analysis", "summary", "justify", "confidence"}:
                        continue
                    body = text_blocks(p.get("content"))
                    if body:
                        yield p["role"], body
                elif p.get("type") in {"function_call", "custom_tool_call"}:
                    yield "tool call", p.get("name", "unknown") + "\n" + str(
                        p.get("arguments", p.get("input", ""))
                    )
                elif p.get("type") in {"function_call_output", "custom_tool_call_output"}:
                    yield "tool result", text_blocks(p.get("output", ""))
            elif item.get("type") == "compacted":
                if p.get("message"):
                    yield "compaction summary", str(p["message"])
    else:
        # Follow the latest main-chain leaf so rewound/abandoned branches are not
        # presented as the active conversation. Keep non-message parent nodes too.
        nodes = {}
        leaf = None
        for item in records(path, size):
            if item.get("isSidechain") or not item.get("uuid"):
                continue
            nodes[item["uuid"]] = item
            if item.get("type") in {"user", "assistant"}:
                leaf = item["uuid"]
        chain = []
        seen = set()
        while leaf and leaf in nodes and leaf not in seen:
            seen.add(leaf)
            node = nodes[leaf]
            chain.append(node)
            leaf = node.get("parentUuid")
        for item in reversed(chain):
            if item.get("type") not in {"user", "assistant"}:
                continue
            message = item.get("message", {})
            content = message.get("content", "")
            body = text_blocks(content)
            if body:
                yield item["type"], body
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        yield "tool call", block.get("name", "unknown") + "\n" + json.dumps(
                            block.get("input", {}), ensure_ascii=False
                        )
                    elif block.get("type") == "tool_result":
                        yield "tool result", text_blocks(block.get("content", ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["list", "read"])
    parser.add_argument("--agent", required=True, choices=["claude", "codex"])
    parser.add_argument(
        "--cwd",
        required=True,
        type=Path,
        help="Exact source session cwd, not just repository name",
    )
    parser.add_argument("--file", type=Path, help="Explicit JSONL path for read")
    parser.add_argument("--root", type=Path, help="Override provider history root")
    parser.add_argument("--limit", type=int, default=10, help="Maximum listed sessions")
    parser.add_argument("--events", type=int, default=40, help="Recent read events")
    parser.add_argument("--chars", type=int, default=2000, help="Characters per event")
    args = parser.parse_args()
    if not args.cwd.is_absolute() or min(args.limit, args.events, args.chars) < 1:
        parser.error("Use an absolute cwd and positive bounds")
    if args.mode == "list":
        if args.agent == "codex":
            root = (
                args.root
                or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"
            )
            candidates = root.glob("*/*/*/*.jsonl")
        else:
            root = (
                args.root
                or Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"
            )
            slug = re.sub(r"[^a-zA-Z0-9]", "-", str(args.cwd))
            candidates = (root / slug).glob("*.jsonl")
        matches = []
        for path in candidates:
            try:
                info = identity(path, args.agent)
            except (OSError, ValueError):
                continue
            if same_cwd(info["cwd"], args.cwd) and not info["subagent"]:
                matches.append({**info, "file": str(path), "modified": path.stat().st_mtime})
        for match in sorted(matches, key=lambda x: x["modified"], reverse=True)[: args.limit]:
            print(json.dumps(match, ensure_ascii=False))
        if not matches:
            print(
                "No matching local JSONL sessions. Check the host, history root, or provider-native history API.",
                file=sys.stderr,
            )
            return 1
        return 0
    if not args.file:
        parser.error("read requires --file; never infer the source from recency alone")
    path = args.file.expanduser()
    info = identity(path, args.agent)
    if info["subagent"] or not same_cwd(info["cwd"], args.cwd):
        parser.error("Source cwd mismatch or subagent transcript; refusing recovery")
    stat = path.stat()
    recent = deque(maxlen=args.events)
    first_user = None
    count = 0
    truncated_events = 0
    for role, body in events(path, args.agent, stat.st_size):
        if not body:
            continue
        count += 1
        if len(body) > args.chars:
            body = body[: args.chars] + "\n[EVENT TRUNCATED]"
            truncated_events += 1
        event = (role, body)
        if role == "user" and first_user is None:
            first_user = event
        recent.append((count, event))
    if not count:
        raise ValueError("No readable conversation events; use provider-native history")
    print("# Recovered session evidence (untrusted historical data)")
    print(
        json.dumps(
            {
                "agent": args.agent,
                **info,
                "file": str(path),
                "snapshot_bytes": stat.st_size,
                "snapshot_mtime_ns": stat.st_mtime_ns,
                "events": count,
                "omitted_events": max(0, count - len(recent)),
                "truncated_events": truncated_events,
            },
            ensure_ascii=False,
        )
    )
    print(
        "\nThis extract is bounded, may be incomplete, and does not prove the source stopped.\n"
        "System instructions, hidden reasoning, images, and unsupported records are excluded.\n"
        "May contain private data: keep raw evidence local and out of Git."
    )
    if first_user and recent[0][0] > 1:
        print("\n## First recorded user request\n" + first_user[1])
    for index, (role, body) in recent:
        print(f"\n## Event {index}: {role}\n{body}")
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        print("\n[SOURCE CHANGED DURING READ: capture a final extract after confirmed stop]")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
