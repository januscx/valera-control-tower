#!/usr/bin/env python3
"""Fail-closed SO-ARM 101 readiness wrapper.

This script records the known controller path and refuses hardware access by
default. The opt-in path does not open serial or send bytes; it only validates
that the requested device path exists and is readable/writable by filesystem
metadata and writes local readiness reports.
"""

from __future__ import annotations

import argparse
import getpass
import grp
import json
import os
import socket
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWN_SO_ARM_DEVICE = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
KNOWN_SO_ARM_TARGET = "../../ttyUSB0"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "so-arm-readiness"
EXIT_FAIL_CLOSED = 2
IDENTITY_BASIS = "operator-confirmed SO-101 motor kit provenance"
PHASE_1_NOTE = "Phase 1 does not open serial and sends no bytes."
SAFETY_FLAGS = {
    "serial_opened": False,
    "serial_commands_sent": False,
    "torque_enabled": False,
    "movement_commanded": False,
    "actuator_calls": False,
}


@dataclass(frozen=True)
class PathReadiness:
    path: str
    exists: bool
    is_symlink: bool
    target: str | None
    resolved_target: str | None
    mode: str | None
    readable: bool
    writable: bool


@dataclass(frozen=True)
class Phase1Status:
    exit_code: int
    status: str
    next_operator_action: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed SO-ARM 101 Phase 1 metadata readiness wrapper. "
            "It never opens serial and never sends bytes."
        ),
        epilog=(
            "Safety boundary: metadata only. This tool does not prove the arm is "
            "safe to move and must not be used for torque, motion, actuator, "
            "LeRobot, or live camera control."
        ),
    )
    parser.add_argument(
        "--device",
        default=KNOWN_SO_ARM_DEVICE,
        help=f"SO-ARM controller path to check; defaults to {KNOWN_SO_ARM_DEVICE}",
    )
    parser.add_argument(
        "--enable-serial-open",
        dest="enable_metadata_check",
        action="store_true",
        help=(
            "Compatibility alias for --enable-metadata-check. This Phase 1 "
            "tool still does not open serial or send bytes."
        ),
    )
    parser.add_argument(
        "--enable-metadata-check",
        action="store_true",
        help=(
            "Explicit operator opt-in for metadata-only readiness reporting. "
            "This does not open serial or send bytes."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for latest.json and latest.md; defaults to {DEFAULT_OUTPUT_DIR}",
    )
    return parser


def inspect_path(
    device: str,
    *,
    stat_fn: Callable[[Path], os.stat_result] = Path.lstat,
    access_fn: Callable[[str, int], bool] = os.access,
    readlink_fn: Callable[[Path], str] = os.readlink,
    resolve_fn: Callable[[Path], Path] = Path.resolve,
) -> PathReadiness:
    path = Path(device)
    try:
        info = stat_fn(path)
    except FileNotFoundError:
        return PathReadiness(
            path=device,
            exists=False,
            is_symlink=False,
            target=None,
            resolved_target=None,
            mode=None,
            readable=False,
            writable=False,
        )

    is_symlink = stat.S_ISLNK(info.st_mode)
    target = readlink_fn(path) if is_symlink else None
    resolved_target = str(resolve_fn(path)) if is_symlink else str(path)
    return PathReadiness(
        path=device,
        exists=True,
        is_symlink=is_symlink,
        target=target,
        resolved_target=resolved_target,
        mode=oct(stat.S_IMODE(info.st_mode)),
        readable=access_fn(device, os.R_OK),
        writable=access_fn(device, os.W_OK),
    )


def determine_phase_1_status(readiness: PathReadiness, *, metadata_check: bool) -> Phase1Status:
    if not metadata_check:
        return Phase1Status(
            exit_code=EXIT_FAIL_CLOSED,
            status="fail_closed",
            next_operator_action=(
                "Run with --enable-metadata-check only when ready to write a "
                "metadata-only report. This still will not open serial or send bytes."
            ),
        )
    if not readiness.exists:
        return Phase1Status(
            exit_code=1,
            status="device_path_missing",
            next_operator_action=(
                "Check USB connection, power, and /dev/serial/by-id path. Do not "
                "open serial or send commands in Phase 1."
            ),
        )
    if not readiness.readable or not readiness.writable:
        return Phase1Status(
            exit_code=0,
            status="metadata_checked_permissions_incomplete",
            next_operator_action=(
                "Phase 2 should check Linux group membership such as dialout and "
                "udev/device permissions. Do not open serial or send commands yet."
            ),
        )
    return Phase1Status(
        exit_code=0,
        status="metadata_checked",
        next_operator_action=(
            "Record this metadata result, then plan protocol/library discovery "
            "before any read/write serial probe."
        ),
    )


def build_report(readiness: PathReadiness, phase_status: Phase1Status) -> dict:
    return {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "groups": current_groups(),
        "known_controller_path": KNOWN_SO_ARM_DEVICE,
        "known_inventory_target": KNOWN_SO_ARM_TARGET,
        "requested_device": readiness.path,
        "resolved_target": readiness.resolved_target,
        "path_metadata": {
            "exists": readiness.exists,
            "is_symlink": readiness.is_symlink,
            "target": readiness.target,
            "mode": readiness.mode,
            "readable": readiness.readable,
            "writable": readiness.writable,
        },
        "identity_basis": IDENTITY_BASIS,
        "status": phase_status.status,
        "exit_code": phase_status.exit_code,
        "next_operator_action": phase_status.next_operator_action,
        "safety_flags": dict(SAFETY_FLAGS),
        "phase_1_note": PHASE_1_NOTE,
    }


def write_reports(report: dict, output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest.json"
    markdown_path = output_dir / "latest.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def current_groups() -> list[dict]:
    groups = []
    for group_id in sorted(set(os.getgroups())):
        try:
            name = grp.getgrgid(group_id).gr_name
        except KeyError:
            name = "unknown"
        groups.append({"gid": group_id, "name": name})
    return groups


def render_markdown(report: dict) -> str:
    metadata = report["path_metadata"]
    safety_flags = report["safety_flags"]
    lines = [
        "# SO-ARM Readiness Phase 1",
        "",
        "## Summary",
        "",
        f"- Timestamp: `{report['timestamp']}`",
        f"- Hostname: `{report['hostname']}`",
        f"- User: `{report['user']}`",
        f"- Known controller path: `{report['known_controller_path']}`",
        f"- Known inventory target: `{report['known_inventory_target']}`",
        f"- Requested device: `{report['requested_device']}`",
        f"- Resolved target: `{report['resolved_target'] or 'n/a'}`",
        f"- Identity basis: {report['identity_basis']}.",
        f"- Status: `{report['status']}`",
        f"- Exit code: `{report['exit_code']}`",
        "",
        "Phase 1 does not open serial and sends no bytes.",
        f"Next operator action: {report['next_operator_action']}",
        "",
        "## Path Metadata",
        "",
        f"- Exists: {metadata['exists']}",
        f"- Symlink: {metadata['is_symlink']}",
        f"- Target: `{metadata['target'] or 'n/a'}`",
        f"- Mode: `{metadata['mode'] or 'n/a'}`",
        f"- Readable by current user: {metadata['readable']}",
        f"- Writable by current user: {metadata['writable']}",
        "",
        "## Groups",
        "",
        *_group_lines(report["groups"]),
        "",
        "## Safety Flags",
        "",
        *[f"- {name}: {str(value).lower()}" for name, value in safety_flags.items()],
        "",
    ]
    return "\n".join(lines)


def render_console_report(
    readiness: PathReadiness,
    *,
    phase_status: Phase1Status,
    report_paths: tuple[Path, Path] | None = None,
) -> str:
    lines = [
        "SO-ARM 101 readiness probe",
        "",
        f"Known controller path: {KNOWN_SO_ARM_DEVICE}",
        f"Known inventory target: {KNOWN_SO_ARM_TARGET}",
        f"Identity basis: {IDENTITY_BASIS}.",
        "",
        f"Requested device: {readiness.path}",
        f"Exists: {readiness.exists}",
        f"Symlink: {readiness.is_symlink}",
        f"Target: {readiness.target or 'n/a'}",
        f"Resolved target: {readiness.resolved_target or 'n/a'}",
        f"Mode: {readiness.mode or 'n/a'}",
        f"Readable by current user: {readiness.readable}",
        f"Writable by current user: {readiness.writable}",
        f"Status: {phase_status.status}",
        f"Exit code: {phase_status.exit_code}",
        "",
        "Safety status:",
        *[f"- {name}: {str(value).lower()}" for name, value in SAFETY_FLAGS.items()],
        "",
        PHASE_1_NOTE,
        "No serial port opened. No bytes sent. Metadata only.",
        f"Next operator action: {phase_status.next_operator_action}",
    ]
    if phase_status.status == "fail_closed":
        lines.extend(
            [
                "",
                "Fail-closed: serial access is disabled by default.",
                "Re-run with --enable-metadata-check to write metadata-only readiness reports.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Opt-in acknowledged: this implementation only checked path metadata.",
            ]
        )
        if report_paths is not None:
            json_path, markdown_path = report_paths
            lines.extend(
                [
                    f"JSON report: {json_path}",
                    f"Markdown report: {markdown_path}",
                ]
            )
    return "\n".join(lines) + "\n"


def _group_lines(groups: list[dict]) -> list[str]:
    if not groups:
        return ["- None reported"]
    return [f"- `{group['name']}` ({group['gid']})" for group in groups]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    readiness = inspect_path(args.device)
    phase_status = determine_phase_1_status(
        readiness,
        metadata_check=args.enable_metadata_check,
    )
    report_paths = None
    if args.enable_metadata_check:
        report = build_report(readiness, phase_status)
        report_paths = write_reports(report, Path(args.output_dir))
    print(
        render_console_report(
            readiness,
            phase_status=phase_status,
            report_paths=report_paths,
        ),
        end="",
    )
    return phase_status.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
