"""Deterministic fixtures for exercising the transport-neutral VR gateway.

The values in this module are simulation fixtures. They are not measurements,
servo limits, or calibration values for Valera hardware.
"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Callable

from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    PosePayload,
    Quaternion,
    SessionStartPayload,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController


SIMULATION_NECK_CONFIG = NeckControlConfig(
    center_pan_degrees=0.0,
    center_tilt_degrees=0.0,
    initial_pan_degrees=0.0,
    initial_tilt_degrees=0.0,
    pan_gain=1.0,
    tilt_gain=1.0,
    filter_time_constant_seconds=0.08,
    max_pan_rate_degrees_per_second=30.0,
    max_tilt_rate_degrees_per_second=20.0,
    min_pan_degrees=-30.0,
    max_pan_degrees=30.0,
    min_tilt_degrees=-20.0,
    max_tilt_degrees=20.0,
)

SIMULATION_SESSION_ID = "simulation-head-session-001"
SIMULATION_START_NS = 1_000_000_000
SIMULATION_SESSION_START_TIMESTAMP_MS = 1_000
SIMULATION_RECENTER_TIMESTAMP_MS = 1_001
SIMULATION_POSE_TIMESTAMP_MS = 1_101


class _SimulationClock:
    def __init__(self, initial_ns: int = SIMULATION_START_NS) -> None:
        self._now_ns = initial_ns

    def __call__(self) -> int:
        return self._now_ns

    def advance_ms(self, milliseconds: int) -> None:
        self._now_ns += milliseconds * 1_000_000


def build_simulated_vr_gateway(clock: Callable[[], int]) -> VrGateway:
    """Build a gateway using only deterministic simulation fixtures."""
    return VrGateway(NeckController(SIMULATION_NECK_CONFIG), clock=clock)


def run_simulated_head_sequence() -> list[dict[str, object]]:
    """Run the fixed head-control flow and return JSON-serializable events."""
    clock = _SimulationClock()
    gateway = build_simulated_vr_gateway(clock)
    outputs = []

    outputs.extend(
        gateway.handle(
            CommandEnvelope(
                "0.1",
                CommandName.SESSION_START,
                SIMULATION_SESSION_ID,
                1,
                SIMULATION_SESSION_START_TIMESTAMP_MS,
                SessionStartPayload("head"),
            )
        )
    )
    outputs.extend(
        gateway.handle(
            CommandEnvelope(
                "0.1",
                CommandName.HEAD_RECENTER,
                SIMULATION_SESSION_ID,
                2,
                SIMULATION_RECENTER_TIMESTAMP_MS,
                PosePayload("quest_local", Quaternion(0.0, 0.0, 0.0, 1.0)),
            )
        )
    )
    clock.advance_ms(100)
    outputs.extend(
        gateway.handle(
            CommandEnvelope(
                "0.1",
                CommandName.HEAD_POSE,
                SIMULATION_SESSION_ID,
                3,
                SIMULATION_POSE_TIMESTAMP_MS,
                PosePayload("quest_local", Quaternion(0.0, 0.1, 0.0, 1.0)),
            )
        )
    )
    clock.advance_ms(250)
    outputs.extend(gateway.poll())

    return [_event_to_dictionary(event) for event in outputs]


def _event_to_dictionary(event: object) -> dict[str, object]:
    return {key: _enum_values(value) for key, value in asdict(event).items()}


def _enum_values(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_values(item) for item in value]
    return value
