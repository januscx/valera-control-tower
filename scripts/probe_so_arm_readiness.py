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
import importlib
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
PHASE_5A_NOTE = (
    "Phase 5A only opens and immediately closes the serial port after explicit "
    "operator opt-in. It sends no bytes and reads no bytes."
)
PHASE_5A_LIMITATIONS = (
    "This does not validate protocol, identity, state, torque, homing, motion "
    "safety, or actuator readiness. Phase 5B must separately review whether "
    "the protocol/library can perform read-only identity/state discovery "
    "without torque, homing, movement, or unsafe writes."
)
PHASE_5B_PLAN_NOTE = (
    "Phase 5B identity/state query is not executed. This planning report opens "
    "no serial port, sends no bytes, and reads no bytes."
)
PHASE_5B_PLAN_LIMITATIONS = (
    "The project has not yet selected and reviewed a non-actuating SO-ARM "
    "identity/state protocol implementation. Feetech PING and READ DATA style "
    "queries are request/response operations, so they require bytes to be sent "
    "before bytes can be read. Do not call this passive read-only unless the "
    "query plan explicitly records bytes written and proves it cannot enable "
    "torque, homing, movement, or actuator state changes."
)
IDENTITY_STATE_PROTOCOL_FINDINGS = {
    "protocol_candidate": "Feetech serial bus servo protocol",
    "library_candidate": "LeRobot Feetech SDK / scservo-compatible SDK",
    "query_requires_bytes": True,
    "torque_required": False,
    "movement_required": False,
    "homing_required": False,
}
IDENTITY_STATE_BLOCKERS = [
    "No LeRobot or Feetech/scservo SDK is installed in the project environment.",
    "No project-owned non-actuating identity/state query implementation exists yet.",
    "Feetech PING/READ DATA style identity/state discovery requires request bytes.",
    "Expected SO-ARM servo ids, baudrate, and response schema have not been verified in project code.",
    "The operator has not completed the wiring/power/pose checklist for query readiness.",
]
IDENTITY_STATE_OPERATOR_PRECONDITIONS = [
    "Confirm CH340 `/dev/ttyUSB0` is the SO-ARM controller path by physical label.",
    "Confirm arm power state is intentional and documented before query work.",
    "Confirm controller board is connected to the correct servo bus.",
    "Confirm servo cable orientation and no loose wires.",
    "Confirm arm is mechanically supported and links/gripper are clear.",
    "Confirm emergency power cut is available and reachable.",
    "Confirm tracks/base are disabled or off-ground if relevant.",
    "Confirm no human fingers are inside pinch or motion zones.",
]
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


@dataclass(frozen=True)
class SerialOpenCloseResult:
    exit_code: int
    status: str
    next_operator_action: str
    serial_open_attempted: bool
    serial_opened: bool
    serial_closed: bool
    serial_backend: str
    serial_timeout_seconds: float
    serial_bytes_written: int
    serial_bytes_read: int
    safety_flags: dict[str, bool]
    limitations: str
    error: str | None = None


@dataclass(frozen=True)
class IdentityStatePlanResult:
    exit_code: int
    status: str
    next_operator_action: str
    phase: str
    mode: str
    execution_available: bool
    protocol_candidate: str
    library_candidate: str
    query_requires_bytes: bool
    torque_required: bool
    movement_required: bool
    homing_required: bool
    safe_to_execute_now: bool
    blockers: list[str]
    operator_preconditions: list[str]
    recommended_next_commands: list[str]
    safety_flags: dict[str, bool]
    limitations: str


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
        "--enable-serial-open-close-check",
        action="store_true",
        help=(
            "Explicit operator opt-in for Phase 5A serial open/close readiness. "
            "This opens the serial port with a timeout, sends no bytes, reads "
            "no bytes, and closes it immediately."
        ),
    )
    parser.add_argument(
        "--plan-identity-state-query",
        action="store_true",
        help=(
            "Write a Phase 5B identity/state query plan only. This does not "
            "open serial, send bytes, read bytes, enable torque, home, or move."
        ),
    )
    parser.add_argument(
        "--serial-timeout-seconds",
        type=float,
        default=0.5,
        help="Timeout for the Phase 5A open/close check; defaults to 0.5 seconds.",
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


def load_serial_factory():
    serial_module = importlib.import_module("serial")
    return getattr(serial_module, "Serial")


def perform_serial_open_close_check(
    readiness: PermissionReadiness,
    *,
    serial_factory=None,
    serial_factory_loader=None,
    timeout_seconds: float = 0.5,
) -> SerialOpenCloseResult:
    base_flags = dict(SAFETY_FLAGS)
    if not readiness.path_exists:
        return SerialOpenCloseResult(
            exit_code=1,
            status="serial_open_close_device_path_missing",
            next_operator_action=(
                "Device path is missing. Do not attempt serial identity/state "
                "work until the operator resolves USB connection and path enumeration."
            ),
            serial_open_attempted=False,
            serial_opened=False,
            serial_closed=False,
            serial_backend="not_loaded",
            serial_timeout_seconds=timeout_seconds,
            serial_bytes_written=0,
            serial_bytes_read=0,
            safety_flags=base_flags,
            limitations=PHASE_5A_LIMITATIONS,
        )
    if not readiness.readable or not readiness.writable:
        return SerialOpenCloseResult(
            exit_code=1,
            status="serial_open_close_permission_blocked",
            next_operator_action=(
                "Current session cannot read/write the device path. Fix operator "
                "permissions before Phase 5A serial contact."
            ),
            serial_open_attempted=False,
            serial_opened=False,
            serial_closed=False,
            serial_backend="not_loaded",
            serial_timeout_seconds=timeout_seconds,
            serial_bytes_written=0,
            serial_bytes_read=0,
            safety_flags=base_flags,
            limitations=PHASE_5A_LIMITATIONS,
        )

    try:
        loader = load_serial_factory if serial_factory_loader is None else serial_factory_loader
        factory = serial_factory if serial_factory is not None else loader()
    except ModuleNotFoundError as exc:
        return SerialOpenCloseResult(
            exit_code=1,
            status="serial_backend_missing",
            next_operator_action=(
                "pyserial is not installed or importable. Do not add hardware "
                "contact until the dependency plan is reviewed."
            ),
            serial_open_attempted=False,
            serial_opened=False,
            serial_closed=False,
            serial_backend="missing_pyserial",
            serial_timeout_seconds=timeout_seconds,
            serial_bytes_written=0,
            serial_bytes_read=0,
            safety_flags=base_flags,
            limitations=PHASE_5A_LIMITATIONS,
            error=str(exc),
        )

    serial_handle = None
    serial_opened = False
    serial_closed = False
    open_error: Exception | None = None
    try:
        serial_handle = factory(
            port=readiness.device_path,
            baudrate=1_000_000,
            timeout=timeout_seconds,
            write_timeout=timeout_seconds,
        )
        serial_opened = True
        base_flags["serial_opened"] = True
    except Exception as exc:
        open_error = exc
    finally:
        if serial_handle is not None:
            try:
                serial_handle.close()
                serial_closed = True
            except Exception as exc:
                open_error = exc
                serial_closed = False

    if serial_opened and serial_closed and open_error is None:
        return SerialOpenCloseResult(
            exit_code=0,
            status="serial_open_close_ready",
            next_operator_action=(
                "Record this open/close evidence. Phase 5B may plan read-only "
                "identity/state discovery, but this result does not validate protocol."
            ),
            serial_open_attempted=True,
            serial_opened=True,
            serial_closed=True,
            serial_backend="pyserial",
            serial_timeout_seconds=timeout_seconds,
            serial_bytes_written=0,
            serial_bytes_read=0,
            safety_flags=base_flags,
            limitations=PHASE_5A_LIMITATIONS,
        )

    if open_error is not None:
        return SerialOpenCloseResult(
            exit_code=1,
            status="serial_open_close_failed",
            next_operator_action=(
                "Serial open/close failed. Keep the system fail-closed and do "
                "not attempt protocol, torque, homing, or movement checks."
            ),
            serial_open_attempted=True,
            serial_opened=serial_opened,
            serial_closed=serial_closed,
            serial_backend="pyserial",
            serial_timeout_seconds=timeout_seconds,
            serial_bytes_written=0,
            serial_bytes_read=0,
            safety_flags=base_flags,
            limitations=PHASE_5A_LIMITATIONS,
            error=f"{type(open_error).__name__}: {open_error}",
        )

    return SerialOpenCloseResult(
        exit_code=1,
        status="serial_open_close_failed",
        next_operator_action=(
            "Serial open/close did not complete. Keep the system fail-closed."
        ),
        serial_open_attempted=True,
        serial_opened=serial_opened,
        serial_closed=serial_closed,
        serial_backend="pyserial",
        serial_timeout_seconds=timeout_seconds,
        serial_bytes_written=0,
        serial_bytes_read=0,
        safety_flags=base_flags,
        limitations=PHASE_5A_LIMITATIONS,
        error="serial open/close did not complete",
    )


def plan_identity_state_query(readiness: PermissionReadiness) -> IdentityStatePlanResult:
    blockers = list(IDENTITY_STATE_BLOCKERS)
    if not readiness.path_exists:
        blockers.insert(0, "SO-ARM serial path is missing.")
    elif not readiness.readable or not readiness.writable:
        blockers.insert(0, "Current session cannot read/write the SO-ARM serial path.")

    return IdentityStatePlanResult(
        exit_code=0,
        status="identity_state_query_planned_blocked",
        next_operator_action=(
            "Complete the wiring checklist and choose a vetted non-actuating "
            "Feetech/LeRobot identity-state query before any live Phase 5B run."
        ),
        phase="5B",
        mode="identity_state_query_plan",
        execution_available=False,
        protocol_candidate=IDENTITY_STATE_PROTOCOL_FINDINGS["protocol_candidate"],
        library_candidate=IDENTITY_STATE_PROTOCOL_FINDINGS["library_candidate"],
        query_requires_bytes=bool(IDENTITY_STATE_PROTOCOL_FINDINGS["query_requires_bytes"]),
        torque_required=bool(IDENTITY_STATE_PROTOCOL_FINDINGS["torque_required"]),
        movement_required=bool(IDENTITY_STATE_PROTOCOL_FINDINGS["movement_required"]),
        homing_required=bool(IDENTITY_STATE_PROTOCOL_FINDINGS["homing_required"]),
        safe_to_execute_now=False,
        blockers=blockers,
        operator_preconditions=list(IDENTITY_STATE_OPERATOR_PRECONDITIONS),
        recommended_next_commands=[
            ".venv/bin/python scripts/probe_so_arm_readiness.py --plan-identity-state-query",
            ".venv/bin/python scripts/probe_so_arm_readiness.py --enable-serial-open-close-check",
        ],
        safety_flags=dict(SAFETY_FLAGS),
        limitations=PHASE_5B_PLAN_LIMITATIONS,
    )


def build_report(
    readiness: PathReadiness,
    phase_status: Phase1Status,
    *,
    permission_readiness: PermissionReadiness | None = None,
    serial_open_close_result: SerialOpenCloseResult | None = None,
    identity_state_plan: IdentityStatePlanResult | None = None,
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
    if serial_open_close_result is not None:
        report.update(
            {
                "phase": "5A",
                "mode": "serial_open_close_check",
                "phase_5a_note": PHASE_5A_NOTE,
                "phase_5a_limitations": PHASE_5A_LIMITATIONS,
                "device_path": permission_readiness.device_path if permission_readiness else readiness.path,
                "resolved_path": (
                    permission_readiness.resolved_path
                    if permission_readiness
                    else readiness.resolved_target
                ),
                "serial_open_attempted": serial_open_close_result.serial_open_attempted,
                "serial_opened": serial_open_close_result.serial_opened,
                "serial_closed": serial_open_close_result.serial_closed,
                "serial_backend": serial_open_close_result.serial_backend,
                "serial_timeout_seconds": serial_open_close_result.serial_timeout_seconds,
                "serial_bytes_written": serial_open_close_result.serial_bytes_written,
                "serial_bytes_read": serial_open_close_result.serial_bytes_read,
                "serial_error": serial_open_close_result.error,
                "safety_flags": dict(serial_open_close_result.safety_flags),
                "limitations": serial_open_close_result.limitations,
            }
        )
    if identity_state_plan is not None:
        report.update(
            {
                "phase": identity_state_plan.phase,
                "mode": identity_state_plan.mode,
                "phase_5b_note": PHASE_5B_PLAN_NOTE,
                "phase_5b_limitations": identity_state_plan.limitations,
                "device_path": permission_readiness.device_path if permission_readiness else readiness.path,
                "resolved_path": (
                    permission_readiness.resolved_path
                    if permission_readiness
                    else readiness.resolved_target
                ),
                "execution_available": identity_state_plan.execution_available,
                "protocol_candidate": identity_state_plan.protocol_candidate,
                "library_candidate": identity_state_plan.library_candidate,
                "query_requires_bytes": identity_state_plan.query_requires_bytes,
                "torque_required": identity_state_plan.torque_required,
                "movement_required": identity_state_plan.movement_required,
                "homing_required": identity_state_plan.homing_required,
                "safe_to_execute_now": identity_state_plan.safe_to_execute_now,
                "blockers": list(identity_state_plan.blockers),
                "operator_preconditions": list(identity_state_plan.operator_preconditions),
                "recommended_next_commands": list(identity_state_plan.recommended_next_commands),
                "safety_flags": dict(identity_state_plan.safety_flags),
                "limitations": identity_state_plan.limitations,
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
    is_phase_5a = report["phase"] == "5A"
    is_phase_5b = report["phase"] == "5B"
    title = "# SO-ARM Readiness Phase 1"
    if is_phase_2:
        title = "# SO-ARM Readiness Phase 2"
    if is_phase_5a:
        title = "# SO-ARM Readiness Phase 5A"
    if is_phase_5b:
        title = "# SO-ARM Readiness Phase 5B Plan"
    phase_note = report.get(
        "phase_5b_note",
        report.get(
            "phase_5a_note",
            report.get("phase_2_note", "Phase 1 does not open serial and sends no bytes."),
        ),
    )
    lines = [
        title,
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
        phase_note,
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
    if is_phase_5a:
        lines.extend(
            [
                "## Serial Open/Close Evidence",
                "",
                f"- Device path: `{report['device_path']}`",
                f"- Resolved path: `{report['resolved_path'] or 'n/a'}`",
                f"- Serial open attempted: {report['serial_open_attempted']}",
                f"- Serial opened: {report['serial_opened']}",
                f"- Serial closed: {report['serial_closed']}",
                f"- Serial backend: `{report['serial_backend']}`",
                f"- Serial timeout seconds: `{report['serial_timeout_seconds']}`",
                f"- Serial bytes written: `{report['serial_bytes_written']}`",
                f"- Serial bytes read: `{report['serial_bytes_read']}`",
                f"- Serial error: `{report['serial_error'] or 'n/a'}`",
                "",
                "## Phase 5A Limitations",
                "",
                report["phase_5a_limitations"],
                "",
            ]
        )
    if is_phase_5b:
        lines.extend(
            [
                "## Identity/State Query Plan",
                "",
                "Identity/state query is not executed in this report.",
                f"- Execution available: {report['execution_available']}",
                f"- Protocol candidate: `{report['protocol_candidate']}`",
                f"- Library candidate: `{report['library_candidate']}`",
                f"- Query requires bytes: {report['query_requires_bytes']}",
                f"- Torque required: {report['torque_required']}",
                f"- Movement required: {report['movement_required']}",
                f"- Homing required: {report['homing_required']}",
                f"- Safe to execute now: {report['safe_to_execute_now']}",
                "",
                "Blockers:",
                "",
                *[f"- {blocker}" for blocker in report["blockers"]],
                "",
                "Operator preconditions:",
                "",
                *[f"- {item}" for item in report["operator_preconditions"]],
                "",
                "Recommended next commands:",
                "",
                *[f"- `{command}`" for command in report["recommended_next_commands"]],
                "",
                "## Phase 5B Limitations",
                "",
                report["phase_5b_limitations"],
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
    serial_open_close_result: SerialOpenCloseResult | None = None,
    identity_state_plan: IdentityStatePlanResult | None = None,
) -> str:
    safety_flags = (
        identity_state_plan.safety_flags
        if identity_state_plan is not None
        else serial_open_close_result.safety_flags
        if serial_open_close_result is not None
        else SAFETY_FLAGS
    )
    phase_note = PHASE_1_NOTE
    no_io_note = "No serial port opened. No bytes sent. Metadata only."
    if permission_readiness is not None:
        phase_note = PHASE_2_NOTE
    if serial_open_close_result is not None:
        phase_note = PHASE_5A_NOTE
        no_io_note = "Serial open/close only. No bytes sent. No bytes read."
    if identity_state_plan is not None:
        phase_note = PHASE_5B_PLAN_NOTE
        no_io_note = "Planning only. No serial port opened. No bytes sent. No bytes read."
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
        *[f"- {name}: {str(value).lower()}" for name, value in safety_flags.items()],
        "",
        phase_note,
        no_io_note,
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
    if serial_open_close_result is not None:
        lines.extend(
            [
                "",
                "Phase 5A serial open/close readiness",
                f"Serial open attempted: {serial_open_close_result.serial_open_attempted}",
                f"Serial opened: {serial_open_close_result.serial_opened}",
                f"Serial closed: {serial_open_close_result.serial_closed}",
                f"Serial backend: {serial_open_close_result.serial_backend}",
                f"Serial timeout seconds: {serial_open_close_result.serial_timeout_seconds}",
                f"Serial bytes written: {serial_open_close_result.serial_bytes_written}",
                f"Serial bytes read: {serial_open_close_result.serial_bytes_read}",
                f"Serial error: {serial_open_close_result.error or 'n/a'}",
                "",
                PHASE_5A_LIMITATIONS,
            ]
        )
    if identity_state_plan is not None:
        lines.extend(
            [
                "",
                "Phase 5B identity/state query plan",
                f"Execution available: {identity_state_plan.execution_available}",
                f"Protocol candidate: {identity_state_plan.protocol_candidate}",
                f"Library candidate: {identity_state_plan.library_candidate}",
                f"Query requires bytes: {identity_state_plan.query_requires_bytes}",
                f"Torque required: {identity_state_plan.torque_required}",
                f"Movement required: {identity_state_plan.movement_required}",
                f"Homing required: {identity_state_plan.homing_required}",
                f"Safe to execute now: {identity_state_plan.safe_to_execute_now}",
                "Blockers:",
                *[f"- {blocker}" for blocker in identity_state_plan.blockers],
                "Operator preconditions:",
                *[f"- {item}" for item in identity_state_plan.operator_preconditions],
                "Recommended next commands:",
                *[f"- {command}" for command in identity_state_plan.recommended_next_commands],
                "",
                PHASE_5B_PLAN_LIMITATIONS,
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
                (
                    "Opt-in acknowledged: this implementation only planned "
                    "identity/state readiness and did not open serial."
                    if identity_state_plan is not None
                    else (
                        "Opt-in acknowledged: this implementation only attempted "
                        "serial open/close and did not read or write bytes."
                        if serial_open_close_result is not None
                        else "Opt-in acknowledged: this implementation only checked path metadata."
                    )
                ),
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
    serial_open_close_result = None
    identity_state_plan = None
    if args.plan_identity_state_query:
        permission_readiness = inspect_permission_readiness(args.device)
        readiness = permission_readiness.path_metadata
        identity_state_plan = plan_identity_state_query(permission_readiness)
        phase_status = Phase1Status(
            exit_code=identity_state_plan.exit_code,
            status=identity_state_plan.status,
            next_operator_action=identity_state_plan.next_operator_action,
        )
    elif args.enable_serial_open_close_check:
        permission_readiness = inspect_permission_readiness(args.device)
        readiness = permission_readiness.path_metadata
        serial_open_close_result = perform_serial_open_close_check(
            permission_readiness,
            timeout_seconds=args.serial_timeout_seconds,
        )
        phase_status = Phase1Status(
            exit_code=serial_open_close_result.exit_code,
            status=serial_open_close_result.status,
            next_operator_action=serial_open_close_result.next_operator_action,
        )
    elif args.enable_permission_check:
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
    if (
        args.enable_metadata_check
        or args.enable_permission_check
        or args.enable_serial_open_close_check
        or args.plan_identity_state_query
    ):
        report = build_report(
            readiness,
            phase_status,
            permission_readiness=permission_readiness,
            serial_open_close_result=serial_open_close_result,
            identity_state_plan=identity_state_plan,
        )
        report_paths = write_reports(report, Path(args.output_dir))
    print(
        render_console_report(
            readiness,
            phase_status=phase_status,
            report_paths=report_paths,
            permission_readiness=permission_readiness,
            serial_open_close_result=serial_open_close_result,
            identity_state_plan=identity_state_plan,
        ),
        end="",
    )
    return phase_status.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
