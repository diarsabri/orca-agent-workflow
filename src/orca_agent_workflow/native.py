"""Discover shared Xcode schemes and run a coordinator-selected native test."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from orca_agent_workflow import task_scope


def preview(root: Path) -> dict | None:
    candidates = sorted([*root.glob("*.xcodeproj"), *root.glob("*.xcworkspace")])
    containers = [path for path in candidates if path.is_dir() and not path.is_symlink()]
    if not containers:
        return None
    schemes = []
    for container in containers:
        for path in sorted(container.glob("xcshareddata/xcschemes/*.xcscheme")):
            entry = {"container": container.name, "scheme": path.stem}
            try:
                if not path.resolve().is_relative_to(root):
                    raise ValueError("scheme resolves outside the project")
                tree = ET.parse(path)
                entry["test_targets"] = sorted({
                    target.attrib["BlueprintName"]
                    for target in tree.findall("./TestAction/Testables/TestableReference/BuildableReference")
                    if target.get("BlueprintName")
                })
                entry["test_plans"] = [
                    plan.get("reference") for plan in tree.findall("./TestAction/TestPlans/TestPlanReference")
                ]
            except (OSError, ValueError, ET.ParseError) as exc:
                entry["problem"] = str(exc)
            schemes.append(entry)
    locks = {*root.glob("Package.resolved"), *root.glob("Podfile.lock"), *root.glob("Cartfile.resolved")}
    for container in containers:
        locks.update(container.glob("xcshareddata/swiftpm/Package.resolved"))
        locks.update(container.glob("project.xcworkspace/xcshareddata/swiftpm/Package.resolved"))
    return {
        "platform": "macOS",
        "containers": [path.name for path in containers],
        "shared_schemes": schemes,
        "dependency_locks": sorted(path.relative_to(root).as_posix() for path in locks if path.is_file()),
        "next": (
            "Review the project, build phases, test plan and dependency setup. "
            "Choose a scheme and simulator explicitly. Pass any required local build artifacts with --requires."
        ),
    }


def checked_output(command: list[str], root: Path) -> str:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or f"{command[0]} failed")
    return result.stdout.strip()


def run(root: Path, args: argparse.Namespace, report: dict) -> None:
    if sys.platform != "darwin":
        raise ValueError("Native Xcode tests require a macOS host with Xcode and an installed simulator.")
    container = root / task_scope.relative(args.container)
    container_flag = {".xcodeproj": "-project", ".xcworkspace": "-workspace"}.get(container.suffix)
    if not container_flag or not container.is_dir() or not container.resolve().is_relative_to(root):
        raise ValueError("Select an existing .xcodeproj or .xcworkspace within the checkout.")
    report["revision"] = task_scope.git_bytes(root, "rev-parse", "HEAD").decode().strip()
    if task_scope.git_bytes(root, "status", "--porcelain"):
        raise ValueError("Run the host check from a clean, committed checkout.")
    missing = [value for value in args.requires if not (root / task_scope.relative(value)).exists()]
    if missing:
        raise ValueError("Missing required local build artifacts: " + ", ".join(missing))

    report["xcode"] = checked_output(["/usr/bin/xcodebuild", "-version"], root)
    output = Path(tempfile.mkdtemp(prefix="orca-native-check-")).resolve()
    log = output / "xcodebuild.log"
    result_bundle = output / "Tests.xcresult"
    report.update(log=str(log), result_bundle=str(result_bundle))
    command = [
        "/usr/bin/xcodebuild", container_flag, str(container), "-scheme", args.scheme,
        "-destination", args.destination, "-derivedDataPath", str(output / "DerivedData"),
        "-resultBundlePath", str(result_bundle), "-disableAutomaticPackageResolution",
        "-parallel-testing-enabled", "NO", "CODE_SIGNING_ALLOWED=NO", "test",
    ]
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
    report["xcode_exit"] = result.returncode
    if not result_bundle.is_dir():
        raise ValueError("Xcode produced no result bundle. Check the log for missing SDKs, simulators or dependencies.")
    summary = json.loads(checked_output([
        "/usr/bin/xcrun", "xcresulttool", "get", "test-results", "summary", "--path", str(result_bundle),
    ], root))
    counts = {name: summary.get(name) for name in ("totalTestCount", "passedTests", "failedTests", "skippedTests")}
    if any(type(count) is not int or count < 0 for count in counts.values()):
        raise ValueError("Xcode did not report valid test counts.")
    report.update(counts)
    report["devices"] = [
        entry.get("device", {}) for entry in summary.get("devicesAndConfigurations", [])
    ]
    if counts["passedTests"] + counts["failedTests"] == 0:
        raise ValueError("Xcode executed zero tests.")
    if result.returncode or counts["failedTests"]:
        raise ValueError("Xcode reported test or build failures.")
    if (
        report["revision"] != task_scope.git_bytes(root, "rev-parse", "HEAD").decode().strip()
        or task_scope.git_bytes(root, "status", "--porcelain")
    ):
        raise ValueError("The checkout changed during the host run.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run reviewed application code and Xcode build phases on the coordinator's macOS host."
    )
    parser.add_argument("--container", required=True, help="Checkout-relative .xcodeproj or .xcworkspace")
    parser.add_argument("--scheme", required=True)
    parser.add_argument("--destination", required=True, help="An explicit simulator destination, such as platform=iOS Simulator,id=UUID")
    parser.add_argument("--requires", action="append", default=[], help="Required checkout-relative local artifact; repeatable")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if not simulator_destination(args.destination) or args.timeout <= 0:
        parser.error("Choose a simulator by ID and a positive timeout.")
    report = {"kind": "macOS host", "scheme": args.scheme, "destination": args.destination, "passed": False}
    try:
        run(task_scope.project_root(), args, report)
        report["passed"] = True
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        report["problem"] = str(exc)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


def simulator_destination(destination: str) -> bool:
    return re.fullmatch(
        r"platform=(?:iOS|watchOS|tvOS|visionOS) Simulator,"
        r"id=[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}",
        destination,
    ) is not None
