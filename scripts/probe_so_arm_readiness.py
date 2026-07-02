#!/usr/bin/env python3
"""Fail-closed SO-ARM 101 readiness wrapper.

This script records the known controller path and refuses hardware access by
default. The opt-in path does not open serial or send bytes; it only validates
that the requested device path exists and is readable/writable by filesystem
metadata.
"""

from __future__ import annotations

import argparse
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


KNOWN_SO_ARM_DEVICE = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
KNOWN_SO_ARM_TARGET = "../../ttyUSB0"
EXIT_FAIL_CLOSED = 2


@dataclass(frozen=True)
class PathReadiness:
    path: str
    exists: bool
    is_symlink: bool
    target: str | None
    mode: str | None
    readable: bool
    writable: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed SO-ARM 101 readiness wrapper.",
    )
    parser.add_argument(
        "--device",
        default=KNOWN_SO_ARM_DEVICE,
        help=f"SO-ARM controller path to check; defaults to {KNOWN_SO_ARM_DEVICE}",
    )
    parser.add_argument(
        "--enable-serial-open",
        action="store_true",
        help=(
            "Explicit operator opt-in for the serial-readiness stage. This "
            "implementation still does not open serial or send bytes."
        ),
    )
    return parser


def inspect_path(
    device: str,
    *,
    stat_fn: Callable[[Path], os.stat_result] = Path.lstat,
    access_fn: Callable[[str, int], bool] = os.access,
    readlink_fn: Callable[[Path], str] = os.readlink,
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
            mode=None,
            readable=False,
            writable=False,
        )

    is_symlink = stat.S_ISLNK(info.st_mode)
    target = readlink_fn(path) if is_symlink else None
    return PathReadiness(
        path=device,
        exists=True,
        is_symlink=is_symlink,
        target=target,
        mode=oct(stat.S_IMODE(info.st_mode)),
        readable=access_fn(device, os.R_OK),
        writable=access_fn(device, os.W_OK),
    )


def render_report(readiness: PathReadiness, *, serial_opt_in: bool) -> str:
    lines = [
        "SO-ARM 101 readiness probe",
        "",
        f"Known controller path: {KNOWN_SO_ARM_DEVICE}",
        f"Known inventory target: {KNOWN_SO_ARM_TARGET}",
        "Identity basis: operator-confirmed SO-101 motor kit provenance.",
        "",
        f"Requested device: {readiness.path}",
        f"Exists: {readiness.exists}",
        f"Symlink: {readiness.is_symlink}",
        f"Target: {readiness.target or 'n/a'}",
        f"Mode: {readiness.mode or 'n/a'}",
        f"Readable by current user: {readiness.readable}",
        f"Writable by current user: {readiness.writable}",
        "",
        "Safety status:",
        "- serial_opened: false",
        "- serial_commands_sent: false",
        "- torque_enabled: false",
        "- movement_commanded: false",
        "- actuator_calls: false",
    ]
    if not serial_opt_in:
        lines.extend(
            [
                "",
                "Fail-closed: serial access is disabled by default.",
                "Re-run with --enable-serial-open only after an operator approves the next stage.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Opt-in acknowledged: this implementation only checked path metadata.",
                "No serial port was opened and no bytes were sent.",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    readiness = inspect_path(args.device)
    print(render_report(readiness, serial_opt_in=args.enable_serial_open), end="")
    if not args.enable_serial_open:
        return EXIT_FAIL_CLOSED
    return 0 if readiness.exists else 1


if __name__ == "__main__":
    raise SystemExit(main())
