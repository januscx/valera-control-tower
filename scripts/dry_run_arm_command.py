#!/usr/bin/env python3
"""Preview intended arm commands without executing hardware actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.arm_commands import (  # noqa: E402
    ArmCommandDryRunResult,
    ArmCommandEnvelope,
    ArmCommandSafetyPrecondition,
    ArmCommandStatus,
    PHASE_4_SAFETY_FLAGS,
    dry_run_arm_command,
)
from robot.adapters.sim_arm import SimArmAdapter  # noqa: E402
from robot.adapters.so_arm_metadata import MetadataOnlySOArmAdapter  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4 dry-run arm command preview. This prints a validation result "
            "and never executes arm commands."
        )
    )
    parser.add_argument(
        "--adapter",
        required=True,
        help="Adapter to validate against.",
    )
    parser.add_argument(
        "--command",
        required=True,
        help="Command intent: noop, home, move-to-pose, open-gripper, close-gripper, hold-position.",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="Human-readable reason for the preview.",
    )
    parser.add_argument(
        "--requested-by",
        default="operator",
        help="Requester label for evidence output.",
    )
    parser.add_argument("--command-id", default="dry-run-arm-command")
    parser.add_argument("--pose-id", help="Named pose for move-to-pose previews.")
    parser.add_argument("--profile", help="Named profile for home previews.")
    parser.add_argument("--width-intent", help="Named gripper width intent.")
    parser.add_argument("--force-profile", help="Named gripper force profile.")
    parser.add_argument("--duration-hint-s", type=float, help="Abstract hold duration hint.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    adapter = _build_adapter(args.adapter)
    if adapter is None:
        result = _invalid_adapter_result(args.adapter, args.command)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 2

    envelope = ArmCommandEnvelope.from_command_name(
        command_id=args.command_id,
        command_name=args.command,
        target=_target_from_args(args),
        reason=args.reason,
        requested_by=args.requested_by,
    )
    result = dry_run_arm_command(envelope, adapter)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.accepted else 2


def _build_adapter(adapter_name: str) -> SimArmAdapter | MetadataOnlySOArmAdapter | None:
    if adapter_name == "sim":
        return SimArmAdapter()
    if adapter_name == "metadata-only-so-arm":
        return MetadataOnlySOArmAdapter()
    return None


def _target_from_args(args: argparse.Namespace) -> dict[str, object]:
    command = args.command.strip().lower().replace("-", "_")
    if command == "home" and args.profile:
        return {"profile": args.profile}
    if command == "move_to_pose":
        return {"pose_id": args.pose_id or "stow"}
    if command == "open_gripper" and args.width_intent:
        return {"width_intent": args.width_intent}
    if command == "close_gripper" and args.force_profile:
        return {"force_profile": args.force_profile}
    if command == "hold_position" and args.duration_hint_s is not None:
        return {"duration_hint_s": args.duration_hint_s}
    return {}


def _invalid_adapter_result(adapter_name: str, command_name: str) -> ArmCommandDryRunResult:
    precondition = ArmCommandSafetyPrecondition(
        name="known_adapter",
        satisfied=False,
        description="Dry-run validation requires a known adapter selection.",
    )
    return ArmCommandDryRunResult(
        command_id="dry-run-arm-command",
        command_type=command_name,
        adapter_id=adapter_name,
        accepted=False,
        executable_now=False,
        status=ArmCommandStatus.REJECTED_SCHEMA,
        schema_valid=False,
        safety_valid=True,
        required_capabilities=[],
        unavailable_capabilities=[],
        safety_preconditions=[precondition],
        evidence={
            "adapter_id": adapter_name,
            "dry_run_status": ArmCommandStatus.REJECTED_SCHEMA.value,
            "blocked_reason": "unknown_adapter",
            "safety_flags": dict(PHASE_4_SAFETY_FLAGS),
        },
        messages=[f"unknown adapter: {adapter_name}"],
        next_actions=["Use sim or metadata-only-so-arm for Phase 4 dry-run previews."],
        safety_flags=dict(PHASE_4_SAFETY_FLAGS),
    )


if __name__ == "__main__":
    raise SystemExit(main())
