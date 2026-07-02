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
import pwd
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
PHASE_2_NOTE = (
    "Phase 2 only checks filesystem/device permissions and operator setup. "
    "This is not a hardware movement readiness result."
)
PHASE_2_LIMITATIONS = (
    "This is not a hardware movement readiness result. This does not confirm "
    "that the arm is safe to move. This does not confirm that the serial "
    "protocol is valid. This does not confirm torque/motor readiness. This "
    "only checks filesystem/device permissions and operator setup."
)
COMMON_SERIAL_GROUPS = {"dialout", "uucp", "tty", "serial", "plugdev"}
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


@dataclass(frozen=True)
class PermissionReadiness:
    path_metadata: PathReadiness
    device_path: str
    resolved_path: str | None
    path_exists: bool
    owner_uid: int | None
    owner_name: str | None
    group_gid: int | None
    group_name: str | None
    mode: str | None
    current_user: str
    current_uid: int
    current_gid: int
    current_groups: list[dict]
    user_in_device_group: bool
    user_listed_in_device_group: bool
    readable: bool
    writable: bool
    common_serial_group: bool
    operator_action_required: bool
    operator_action_reason: str
    recommended_operator_commands: list[str]
    recommended_relogin_required: bool


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
        "--enable-permission-check",
        action="store_true",
        help=(
            "Explicit operator opt-in for Phase 2 permissions/operator "
            "readiness reporting. This does not open serial or send bytes."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for latest.json and latest.md; defaults to {DEFAULT_OUTPUT_DIR}",
    )
    return parser


def _name_for_uid(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return "unknown"


def _name_for_gid(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return "unknown"


def _group_members_for_gid(gid: int) -> list[str]:
    try:
        return list(getattr(grp.getgrgid(gid), "gr_mem", []))
    except KeyError:
        return []


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


def inspect_permission_readiness(
    device: str,
    *,
    stat_fn: Callable[[Path], os.stat_result] = Path.stat,
    access_fn: Callable[[str, int], bool] = os.access,
) -> PermissionReadiness:
    path_metadata = inspect_path(device, access_fn=access_fn)
    current_user = getpass.getuser()
    current_uid = os.getuid()
    current_gid = os.getgid()
    groups = current_groups()
    group_ids = {group["gid"] for group in groups}

    if not path_metadata.exists:
        return PermissionReadiness(
            path_metadata=path_metadata,
            device_path=device,
            resolved_path=path_metadata.resolved_target,
            path_exists=False,
            owner_uid=None,
            owner_name=None,
            group_gid=None,
            group_name=None,
            mode=None,
            current_user=current_user,
            current_uid=current_uid,
            current_gid=current_gid,
            current_groups=groups,
            user_in_device_group=False,
            user_listed_in_device_group=False,
            readable=False,
            writable=False,
            common_serial_group=False,
            operator_action_required=True,
            operator_action_reason=(
                "Device path does not exist. Check USB connection, power, cable, "
                "and serial device enumeration."
            ),
            recommended_operator_commands=["ls -l /dev/ttyUSB* /dev/ttyACM*"],
            recommended_relogin_required=False,
        )

    info = stat_fn(Path(device))
    owner_uid = info.st_uid
    group_gid = info.st_gid
    group_name = _name_for_gid(group_gid)
    readable = access_fn(device, os.R_OK)
    writable = access_fn(device, os.W_OK)
    user_in_device_group = group_gid in group_ids
    user_listed_in_device_group = current_user in _group_members_for_gid(group_gid)
    common_serial_group = group_name in COMMON_SERIAL_GROUPS

    commands: list[str] = []
    relogin_required = False
    action_required = False
    if not readable or not writable:
        action_required = True
        if group_name != "unknown" and user_listed_in_device_group and not user_in_device_group:
            relogin_required = True
            reason = (
                f"Current user is listed in the device group `{group_name}`, "
                "but this session does not have that supplementary group yet. "
                "Log out and back in, or reboot, before the future serial "
                "identity phase."
            )
        elif group_name != "unknown" and not user_in_device_group:
            commands.append(f'sudo usermod -aG {group_name} "$USER"')
            relogin_required = True
            reason = (
                f"Current user is not in the device group `{group_name}`, and "
                "the device is not readable/writable by the current session."
            )
        elif group_name == "unknown":
            reason = (
                "Device group could not be resolved. Inspect udev rules and "
                "document the device ownership before any future serial phase."
            )
        else:
            reason = (
                "Current user appears to be in the device group, but the device "
                "is not readable/writable by the current session. Re-login may "
                "be needed if group membership changed recently; otherwise "
                "inspect udev permissions."
            )
    elif group_name != "unknown" and not user_in_device_group:
        action_required = True
        commands.append(f'sudo usermod -aG {group_name} "$USER"')
        relogin_required = True
        reason = (
            f"Device is currently accessible, but current group membership does "
            f"not include `{group_name}`. Add the operator to the group for a "
            "stable future serial identity phase."
        )
    else:
        reason = (
            "Operator permissions look ready for a future serial identity phase. "
            "This does not imply protocol, torque, or motion readiness."
        )

    if action_required and group_name != "unknown" and not common_serial_group:
        reason += " The device group is not a common serial-access group; inspect udev rules."

    return PermissionReadiness(
        path_metadata=path_metadata,
        device_path=device,
        resolved_path=path_metadata.resolved_target,
        path_exists=True,
        owner_uid=owner_uid,
        owner_name=_name_for_uid(owner_uid),
        group_gid=group_gid,
        group_name=group_name,
        mode=oct(stat.S_IMODE(info.st_mode)),
        current_user=current_user,
        current_uid=current_uid,
        current_gid=current_gid,
        current_groups=groups,
        user_in_device_group=user_in_device_group,
        user_listed_in_device_group=user_listed_in_device_group,
        readable=readable,
        writable=writable,
        common_serial_group=common_serial_group,
        operator_action_required=action_required,
        operator_action_reason=reason,
        recommended_operator_commands=commands,
        recommended_relogin_required=relogin_required,
    )


def determine_phase_2_status(readiness: PermissionReadiness) -> Phase1Status:
    if not readiness.path_exists:
        return Phase1Status(
            exit_code=1,
            status="permission_check_device_path_missing",
            next_operator_action=readiness.operator_action_reason,
        )
    if readiness.operator_action_required:
        return Phase1Status(
            exit_code=0,
            status="permission_check_operator_action_required",
            next_operator_action=readiness.operator_action_reason,
        )
    return Phase1Status(
        exit_code=0,
        status="permission_check_ready_for_future_identity_phase",
        next_operator_action=readiness.operator_action_reason,
    )


def build_report(
    readiness: PathReadiness,
    phase_status: Phase1Status,
    *,
    permission_readiness: PermissionReadiness | None = None,
) -> dict:
    report = {
        "schema_version": 1,
        "phase": "phase_1_metadata",
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
    if permission_readiness is not None:
        report.update(
            {
                "phase": "phase_2_permissions_operator_readiness",
                "phase_2_note": PHASE_2_NOTE,
                "phase_2_limitations": PHASE_2_LIMITATIONS,
                "device_path": permission_readiness.device_path,
                "resolved_path": permission_readiness.resolved_path,
                "path_exists": permission_readiness.path_exists,
                "owner_uid": permission_readiness.owner_uid,
                "owner_name": permission_readiness.owner_name,
                "group_gid": permission_readiness.group_gid,
                "group_name": permission_readiness.group_name,
                "mode": permission_readiness.mode,
                "current_user": permission_readiness.current_user,
                "current_uid": permission_readiness.current_uid,
                "current_gid": permission_readiness.current_gid,
                "current_groups": permission_readiness.current_groups,
                "user_in_device_group": permission_readiness.user_in_device_group,
                "user_listed_in_device_group": permission_readiness.user_listed_in_device_group,
                "readable": permission_readiness.readable,
                "writable": permission_readiness.writable,
                "operator_action_required": permission_readiness.operator_action_required,
                "operator_action_reason": permission_readiness.operator_action_reason,
                "recommended_operator_commands": permission_readiness.recommended_operator_commands,
                "recommended_relogin_required": permission_readiness.recommended_relogin_required,
                "operator_readiness": {
                    "current_user": permission_readiness.current_user,
                    "current_uid": permission_readiness.current_uid,
                    "current_gid": permission_readiness.current_gid,
                    "current_groups": permission_readiness.current_groups,
                    "user_in_device_group": permission_readiness.user_in_device_group,
                    "user_listed_in_device_group": permission_readiness.user_listed_in_device_group,
                    "readable": permission_readiness.readable,
                    "writable": permission_readiness.writable,
                    "common_serial_group": permission_readiness.common_serial_group,
                    "operator_action_required": permission_readiness.operator_action_required,
                    "operator_action_reason": permission_readiness.operator_action_reason,
                    "recommended_operator_commands": permission_readiness.recommended_operator_commands,
                    "recommended_relogin_required": permission_readiness.recommended_relogin_required,
                },
            }
        )
    return report


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
    is_phase_2 = report["phase"] == "phase_2_permissions_operator_readiness"
    lines = [
        "# SO-ARM Readiness Phase 2" if is_phase_2 else "# SO-ARM Readiness Phase 1",
        "",
        "## Summary",
        "",
        f"- Phase: `{report['phase']}`",
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
        report.get("phase_2_note", "Phase 1 does not open serial and sends no bytes."),
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
    ]
    if is_phase_2:
        commands = report["recommended_operator_commands"]
        lines.extend(
            [
                "## Operator Readiness",
                "",
                f"- Device path: `{report['device_path']}`",
                f"- Resolved path: `{report['resolved_path'] or 'n/a'}`",
                f"- Path exists: {report['path_exists']}",
                f"- Owner: `{report['owner_name'] or 'n/a'}` ({report['owner_uid']})",
                f"- Group: `{report['group_name'] or 'n/a'}` ({report['group_gid']})",
                f"- Mode: `{report['mode'] or 'n/a'}`",
                f"- Current user: `{report['current_user']}`",
                f"- Current uid/gid: `{report['current_uid']}` / `{report['current_gid']}`",
                f"- User in device group: {report['user_in_device_group']}",
                f"- User listed in device group: {report['user_listed_in_device_group']}",
                f"- Readable: {report['readable']}",
                f"- Writable: {report['writable']}",
                f"- Operator action required: {report['operator_action_required']}",
                f"- Operator action reason: {report['operator_action_reason']}",
                f"- Relogin/reboot required: {report['recommended_relogin_required']}",
                "",
                "Recommended operator commands:",
                "",
                *(f"- `{command}`" for command in commands),
                *(["- None"] if not commands else []),
                "",
                "## Phase 2 Limitations",
                "",
                report["phase_2_limitations"],
                "",
            ]
        )
    lines.extend(
        [
        "## Groups",
        "",
        *_group_lines(report["groups"]),
        "",
        "## Safety Flags",
        "",
        *[f"- {name}: {str(value).lower()}" for name, value in safety_flags.items()],
        "",
        ]
    )
    return "\n".join(lines)


def render_console_report(
    readiness: PathReadiness,
    *,
    phase_status: Phase1Status,
    report_paths: tuple[Path, Path] | None = None,
    permission_readiness: PermissionReadiness | None = None,
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
        PHASE_2_NOTE if permission_readiness is not None else PHASE_1_NOTE,
        "No serial port opened. No bytes sent. Metadata only.",
        f"Next operator action: {phase_status.next_operator_action}",
    ]
    if permission_readiness is not None:
        commands = permission_readiness.recommended_operator_commands
        lines.extend(
            [
                "",
                "Phase 2 permission/operator readiness",
                f"Device path: {permission_readiness.device_path}",
                f"Resolved path: {permission_readiness.resolved_path or 'n/a'}",
                f"Owner: {permission_readiness.owner_name or 'n/a'} ({permission_readiness.owner_uid})",
                f"Group: {permission_readiness.group_name or 'n/a'} ({permission_readiness.group_gid})",
                f"Mode: {permission_readiness.mode or 'n/a'}",
                f"Current user: {permission_readiness.current_user}",
                f"Current uid/gid: {permission_readiness.current_uid}/{permission_readiness.current_gid}",
                f"User in device group: {permission_readiness.user_in_device_group}",
                f"User listed in device group: {permission_readiness.user_listed_in_device_group}",
                f"Operator action required: {permission_readiness.operator_action_required}",
                f"Operator action reason: {permission_readiness.operator_action_reason}",
                f"Recommended operator commands: {', '.join(commands) if commands else 'none'}",
                f"Relogin/reboot required: {permission_readiness.recommended_relogin_required}",
                "",
                PHASE_2_LIMITATIONS,
            ]
        )
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
    permission_readiness = None
    if args.enable_permission_check:
        permission_readiness = inspect_permission_readiness(args.device)
        readiness = permission_readiness.path_metadata
        phase_status = determine_phase_2_status(permission_readiness)
    else:
        readiness = inspect_path(args.device)
        phase_status = determine_phase_1_status(
            readiness,
            metadata_check=args.enable_metadata_check,
        )
    report_paths = None
    if args.enable_metadata_check or args.enable_permission_check:
        report = build_report(
            readiness,
            phase_status,
            permission_readiness=permission_readiness,
        )
        report_paths = write_reports(report, Path(args.output_dir))
    print(
        render_console_report(
            readiness,
            phase_status=phase_status,
            report_paths=report_paths,
            permission_readiness=permission_readiness,
        ),
        end="",
    )
    return phase_status.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
