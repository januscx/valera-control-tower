#!/usr/bin/env python3
"""Collect a read-only local hardware inventory for Valera bring-up planning."""

from __future__ import annotations

import getpass
import glob
import grp
import json
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "hardware-inventory"
SAFE_COMMANDS = ("lsusb", "v4l2-ctl", "udevadm", "python3", "lspci")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str]], CommandResult]
CommandResolver = Callable[[str], str | None]


def default_command_runner(args: list[str]) -> CommandResult:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def collect_inventory(
    *,
    dev_root: Path = Path("/dev"),
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    command_runner: CommandRunner = default_command_runner,
    command_resolver: CommandResolver = shutil.which,
    now: Callable[[], datetime] | None = None,
) -> dict:
    """Collect inventory metadata without opening camera or serial devices."""
    timestamp = (now or _utc_now)().astimezone(timezone.utc).isoformat()
    errors: list[str] = []
    commands = _available_commands(command_resolver)

    report = {
        "schema_version": 1,
        "timestamp": timestamp,
        "hostname": _safe_call(socket.gethostname, errors, "hostname"),
        "current_user": _safe_call(getpass.getuser, errors, "current_user"),
        "groups": _current_groups(errors),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "kernel": platform.release(),
        "devices": {
            "video": _glob_devices(dev_root, "video*", errors),
            "tty": _glob_devices(dev_root, "tty*", errors),
            "serial_by_id": _glob_devices(dev_root / "serial" / "by-id", "*", errors),
            "serial_by_path": _glob_devices(dev_root / "serial" / "by-path", "*", errors),
        },
        "commands": commands,
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "cv2": _cv2_status(errors),
        "usb_devices": _run_optional_command(["lsusb"], commands, command_runner),
        "pci_devices": _run_optional_command(["lspci"], commands, command_runner),
        "v4l2_devices": _run_optional_command(
            ["v4l2-ctl", "--list-devices"], commands, command_runner
        ),
        "output_paths": {
            "json": str(output_dir / "latest.json"),
            "markdown": str(output_dir / "latest.md"),
        },
        "safety": {
            "inventory_only": True,
            "opened_camera": False,
            "captured_frames": False,
            "opened_serial_ports": False,
            "sent_serial_commands": False,
            "enabled_torque": False,
            "moved_robot": False,
            "controlled_arm": False,
            "called_actuators": False,
        },
        "errors": errors,
    }
    report["candidates"] = _candidate_notes(report)
    return report


def write_reports(report: dict, output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest.json"
    markdown_path = output_dir / "latest.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: dict) -> str:
    devices = report["devices"]
    commands = report["commands"]
    candidates = report["candidates"]

    lines = [
        "# Hardware Inventory v0",
        "",
        "## Summary",
        "",
        f"- Timestamp: `{report['timestamp']}`",
        f"- Hostname: `{report['hostname']}`",
        f"- Current user: `{report['current_user']}`",
        f"- Platform: `{report['platform']['platform']}`",
        f"- Video devices: {len(devices['video'])}",
        f"- TTY devices: {len(devices['tty'])}",
        f"- Serial by-id devices: {len(devices['serial_by_id'])}",
        f"- Serial by-path devices: {len(devices['serial_by_path'])}",
        "",
        "Safety note: inventory only, no devices opened, no commands sent.",
        "",
        "## Video Devices",
        "",
        *_device_lines(devices["video"]),
        "",
        "## Serial Devices",
        "",
        "### /dev/tty*",
        "",
        *_device_lines(devices["tty"]),
        "",
        "### /dev/serial/by-id",
        "",
        *_device_lines(devices["serial_by_id"]),
        "",
        "### /dev/serial/by-path",
        "",
        *_device_lines(devices["serial_by_path"]),
        "",
        "## USB Devices",
        "",
        *_command_output_lines(report["usb_devices"]),
        "",
        "## Permissions / Groups",
        "",
        *_group_lines(report["groups"]),
        "",
        "## Optional Commands",
        "",
        *_command_availability_lines(commands),
        "",
        "## Candidate Notes",
        "",
        *_candidate_lines(candidates),
        "",
        "## v4l2 Devices",
        "",
        *_command_output_lines(report["v4l2_devices"]),
        "",
        "## Errors",
        "",
        *_plain_lines(report["errors"], empty="- None recorded"),
        "",
    ]
    return "\n".join(lines)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_call(func: Callable[[], str], errors: list[str], label: str) -> str:
    try:
        return func()
    except Exception as exc:  # pragma: no cover - defensive around platform calls
        errors.append(f"{label}: {exc}")
        return "unknown"


def _current_groups(errors: list[str]) -> list[dict]:
    try:
        group_ids = sorted(set(getattr(__import__("os"), "getgroups")()))
        groups = []
        for group_id in group_ids:
            try:
                name = grp.getgrgid(group_id).gr_name
            except KeyError:
                name = "unknown"
            groups.append({"gid": group_id, "name": name})
        return groups
    except Exception as exc:  # pragma: no cover - defensive around OS differences
        errors.append(f"groups: {exc}")
        return []


def _glob_devices(root: Path, pattern: str, errors: list[str]) -> list[dict]:
    try:
        paths = sorted(Path(path) for path in glob.glob(str(root / pattern)))
    except Exception as exc:
        errors.append(f"glob {root / pattern}: {exc}")
        return []

    devices = []
    for path in paths:
        devices.append(_describe_path(path, errors))
    return devices


def _describe_path(path: Path, errors: list[str]) -> dict:
    info = {
        "path": str(path),
        "name": path.name,
        "exists": path.exists(),
        "is_symlink": path.is_symlink(),
        "target": None,
        "mode": None,
        "uid": None,
        "gid": None,
        "group": None,
    }
    try:
        if path.is_symlink():
            info["target"] = str(path.readlink())
        stat_result = path.lstat()
        info["mode"] = oct(stat_result.st_mode & 0o7777)
        info["uid"] = stat_result.st_uid
        info["gid"] = stat_result.st_gid
        try:
            info["group"] = grp.getgrgid(stat_result.st_gid).gr_name
        except KeyError:
            info["group"] = "unknown"
    except Exception as exc:
        errors.append(f"stat {path}: {exc}")
    return info


def _available_commands(command_resolver: CommandResolver) -> dict:
    commands = {}
    for name in SAFE_COMMANDS:
        resolved = command_resolver(name)
        commands[name] = {"available": resolved is not None, "path": resolved}
    return commands


def _run_optional_command(
    args: list[str], commands: dict, command_runner: CommandRunner
) -> dict:
    command_name = args[0]
    if not commands.get(command_name, {}).get("available"):
        return {
            "command": args,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    try:
        result = command_runner(args)
        return {
            "command": args,
            "available": True,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as exc:
        return {
            "command": args,
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }


def _cv2_status(errors: list[str]) -> dict:
    try:
        import cv2  # type: ignore

        return {
            "imports": True,
            "version": getattr(cv2, "__version__", "unknown"),
            "aruco_available": hasattr(cv2, "aruco"),
        }
    except Exception as exc:
        return {"imports": False, "version": None, "aruco_available": False, "error": str(exc)}


def _candidate_notes(report: dict) -> dict:
    text_sources = [
        report["usb_devices"].get("stdout", ""),
        report["v4l2_devices"].get("stdout", ""),
        " ".join(device["path"] for device in report["devices"]["video"]),
        " ".join(device["path"] for device in report["devices"]["serial_by_id"]),
        " ".join(device["path"] for device in report["devices"]["serial_by_path"]),
    ]
    combined = "\n".join(text_sources).lower()
    serial_paths = report["devices"]["serial_by_id"] + report["devices"]["serial_by_path"]

    return {
        "possible_orbbec_camera": _possible(
            any(marker in combined for marker in ("orbbec", "astra", "gemini", "depth"))
            or bool(report["devices"]["video"]),
            "Video devices or USB/video names may indicate a camera. Confirm manually before use.",
        ),
        "possible_so_arm_serial": _possible(
            any(_serial_name_matches(device, ("so-arm", "so_arm", "servo", "dynamixel", "lerobot"))
                for device in serial_paths),
            "Serial by-id/by-path names may indicate an arm controller. This is heuristic only.",
        ),
        "possible_tracked_base_serial": _possible(
            any(_serial_name_matches(device, ("base", "chassis", "motor", "roboclaw", "sabertooth"))
                for device in serial_paths),
            "Serial by-id/by-path names may indicate a base controller. This is heuristic only.",
        ),
    }


def _possible(is_candidate: bool, note: str) -> dict:
    return {"candidate": bool(is_candidate), "note": note}


def _serial_name_matches(device: dict, markers: Iterable[str]) -> bool:
    haystack = f"{device.get('path', '')} {device.get('target', '')}".lower()
    return any(marker in haystack for marker in markers)


def _device_lines(devices: list[dict]) -> list[str]:
    if not devices:
        return ["- None found"]
    lines = []
    for device in devices:
        target = f" -> `{device['target']}`" if device.get("target") else ""
        group = f", group `{device['group']}`" if device.get("group") else ""
        mode = f", mode `{device['mode']}`" if device.get("mode") else ""
        lines.append(f"- `{device['path']}`{target}{mode}{group}")
    return lines


def _command_output_lines(result: dict) -> list[str]:
    if not result.get("available"):
        return [f"- `{result['command'][0]}` unavailable"]
    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()
    if not stdout and not stderr:
        return [f"- `{ ' '.join(result['command']) }` returned no output"]
    lines = [f"Command: `{' '.join(result['command'])}`"]
    if stdout:
        lines.extend(["", "```text", stdout, "```"])
    if stderr:
        lines.extend(["", "stderr:", "", "```text", stderr, "```"])
    return lines


def _group_lines(groups: list[dict]) -> list[str]:
    if not groups:
        return ["- No groups reported"]
    return [f"- `{group['name']}` ({group['gid']})" for group in groups]


def _command_availability_lines(commands: dict) -> list[str]:
    return [
        f"- `{name}`: {'available' if data['available'] else 'unavailable'}"
        + (f" at `{data['path']}`" if data.get("path") else "")
        for name, data in sorted(commands.items())
    ]


def _candidate_lines(candidates: dict) -> list[str]:
    lines = []
    for label, data in candidates.items():
        status = "candidate" if data["candidate"] else "not identified"
        lines.append(f"- `{label}`: {status}. {data['note']}")
    return lines


def _plain_lines(values: list[str], *, empty: str) -> list[str]:
    if not values:
        return [empty]
    return [f"- {value}" for value in values]


def main() -> int:
    try:
        report = collect_inventory()
    except Exception as exc:  # pragma: no cover - last-resort reporting path
        report = {
            "schema_version": 1,
            "timestamp": _utc_now().isoformat(),
            "hostname": "unknown",
            "current_user": "unknown",
            "groups": [],
            "platform": {"platform": platform.platform()},
            "kernel": platform.release(),
            "devices": {"video": [], "tty": [], "serial_by_id": [], "serial_by_path": []},
            "commands": _available_commands(shutil.which),
            "python": {"executable": sys.executable, "version": sys.version},
            "cv2": {"imports": False, "version": None, "aruco_available": False},
            "usb_devices": {"command": ["lsusb"], "available": False, "stdout": "", "stderr": ""},
            "pci_devices": {"command": ["lspci"], "available": False, "stdout": "", "stderr": ""},
            "v4l2_devices": {
                "command": ["v4l2-ctl", "--list-devices"],
                "available": False,
                "stdout": "",
                "stderr": "",
            },
            "output_paths": {
                "json": str(DEFAULT_OUTPUT_DIR / "latest.json"),
                "markdown": str(DEFAULT_OUTPUT_DIR / "latest.md"),
            },
            "safety": {
                "inventory_only": True,
                "opened_camera": False,
                "captured_frames": False,
                "opened_serial_ports": False,
                "sent_serial_commands": False,
                "enabled_torque": False,
                "moved_robot": False,
                "controlled_arm": False,
                "called_actuators": False,
            },
            "errors": [f"collector: {exc}"],
            "candidates": {},
        }

    try:
        json_path, markdown_path = write_reports(report)
    except Exception as exc:
        print(f"failed to write hardware inventory reports: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
