from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    EmptyPayload,
    GatewayState,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
    NeckTargetEvent,
    OutputEvent,
    PosePayload,
    RejectionCode,
    SafetyStopEvent,
    SessionStartPayload,
    StopReason,
    validate_command_envelope,
)
from robot.vr_gateway.neck import NeckController


@dataclass(frozen=True)
class GatewayConfig:
    handshake_timeout_ns: int = 10_000_000_000
    motion_watchdog_timeout_ns: int = 250_000_000


_REJECTION_MESSAGES = {
    RejectionCode.STALE_SEQUENCE: "Sequence must increase within the session.",
    RejectionCode.STALE_TIMESTAMP: "Timestamp must not decrease within the session.",
    RejectionCode.SESSION_MISMATCH: "Command does not match the active session.",
    RejectionCode.NO_ACTIVE_SESSION: "No active session is available.",
    RejectionCode.MODE_BLOCKED: "Requested operation is blocked in this mode.",
    RejectionCode.UNKNOWN_MODE: "Requested mode is not recognized.",
    RejectionCode.WATCHDOG_ACTIVE: "The motion watchdog is active.",
    RejectionCode.INVALID_PAYLOAD: "Command payload is invalid.",
    RejectionCode.ESTOP_LATCHED: "Emergency stop is latched.",
}


class VrGateway:
    def __init__(
        self,
        neck_controller: NeckController,
        clock: Callable[[], int] = time.monotonic_ns,
        config: GatewayConfig = GatewayConfig(),
    ) -> None:
        self.neck_controller = neck_controller
        self.clock = clock
        self.config = config
        self.state = GatewayState.IDLE
        self.used_session_ids: set[str] = set()
        self.active_session_id: str | None = None
        self.last_sequence: int | None = None
        self.last_timestamp_ms: int | None = None
        self.session_started_monotonic_ns: int | None = None
        self.last_valid_packet_received_monotonic_ns: int | None = None

    def handle(self, command: object) -> tuple[OutputEvent, ...]:
        now_ns = self.clock()

        try:
            command = validate_command_envelope(command)
        except (MessageValidationError, AttributeError, TypeError, ValueError):
            deadline_events = self._evaluate_deadline(now_ns)
            return deadline_events + (
                self._reject_untrusted(command, RejectionCode.INVALID_PAYLOAD, now_ns),
            )

        if command.command is CommandName.EMERGENCY_STOP:
            if type(command.payload) is not EmptyPayload:
                return (self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),)
            return self._handle_emergency_stop(command, now_ns)

        deadline_events = self._evaluate_deadline(now_ns)
        if deadline_events:
            code = (
                RejectionCode.WATCHDOG_ACTIVE
                if self.state is GatewayState.SAFE_STOPPED
                else RejectionCode.NO_ACTIVE_SESSION
            )
            return deadline_events + (self._reject(command, code, now_ns),)

        if command.command is CommandName.SESSION_START:
            return self._handle_session_start(command, now_ns)

        if self.state is GatewayState.SAFE_STOPPED:
            return (self._reject(command, RejectionCode.WATCHDOG_ACTIVE, now_ns),)
        if self.active_session_id is None:
            return (self._reject(command, RejectionCode.NO_ACTIVE_SESSION, now_ns),)
        if command.session_id != self.active_session_id:
            return (self._reject(command, RejectionCode.SESSION_MISMATCH, now_ns),)
        if self.last_sequence is not None and command.sequence <= self.last_sequence:
            return (self._reject(command, RejectionCode.STALE_SEQUENCE, now_ns),)
        if (
            self.last_timestamp_ms is not None
            and command.timestamp_ms < self.last_timestamp_ms
        ):
            return (self._reject(command, RejectionCode.STALE_TIMESTAMP, now_ns),)

        expected_payload = {
            CommandName.SESSION_STOP: EmptyPayload,
            CommandName.MODE_SET: ModeSetPayload,
            CommandName.HEAD_POSE: PosePayload,
            CommandName.HEAD_RECENTER: PosePayload,
        }.get(command.command)
        if expected_payload is None or type(command.payload) is not expected_payload:
            return (self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),)

        if command.command is CommandName.MODE_SET:
            return self._handle_mode_set(command, now_ns)
        if command.command is CommandName.HEAD_RECENTER:
            return self._handle_recenter(command, now_ns)
        if command.command is CommandName.HEAD_POSE:
            return self._handle_pose(command, now_ns)
        return self._handle_session_stop(command, now_ns)

    def poll(self) -> tuple[OutputEvent, ...]:
        now_ns = self.clock()
        return self._evaluate_deadline(now_ns)

    def _evaluate_deadline(self, now_ns: int) -> tuple[OutputEvent, ...]:
        if (
            self.state is GatewayState.AWAITING_RECENTER
            and self.session_started_monotonic_ns is not None
            and now_ns - self.session_started_monotonic_ns
            >= self.config.handshake_timeout_ns
        ):
            session_id = self.active_session_id
            sequence = self.last_sequence
            transition = self._transition(
                GatewayState.IDLE, session_id, sequence, now_ns
            )
            self._invalidate_active_session()
            return (transition,) if transition is not None else ()

        if (
            self.state is GatewayState.HEAD_ACTIVE
            and self.last_valid_packet_received_monotonic_ns is not None
            and now_ns - self.last_valid_packet_received_monotonic_ns
            >= self.config.motion_watchdog_timeout_ns
        ):
            session_id = self.active_session_id
            sequence = self.last_sequence
            transition = self._transition(
                GatewayState.SAFE_STOPPED, session_id, sequence, now_ns
            )
            stop = SafetyStopEvent(
                now_ns,
                StopReason.WATCHDOG,
                session_id,
                sequence,
            )
            self._invalidate_active_session()
            return (transition, stop) if transition is not None else (stop,)

        return ()

    def _handle_session_start(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        if self.state is GatewayState.ESTOP_LATCHED:
            return (self._reject(command, RejectionCode.ESTOP_LATCHED, now_ns),)
        if not isinstance(command.payload, SessionStartPayload) or command.sequence != 1:
            return (self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),)
        if command.session_id in self.used_session_ids:
            return (self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),)
        if command.payload.requested_mode in {"drive", "arm"}:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        if command.payload.requested_mode != "head":
            return (self._reject(command, RejectionCode.UNKNOWN_MODE, now_ns),)

        self.used_session_ids.add(command.session_id)
        self.active_session_id = command.session_id
        self.last_sequence = command.sequence
        self.last_timestamp_ms = command.timestamp_ms
        self.session_started_monotonic_ns = now_ns
        self.last_valid_packet_received_monotonic_ns = now_ns
        transition = self._transition(
            GatewayState.AWAITING_RECENTER,
            command.session_id,
            command.sequence,
            now_ns,
        )
        return (transition,) if transition is not None else ()

    def _handle_mode_set(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, ModeSetPayload)
        if command.payload.mode in {"drive", "arm"}:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        if command.payload.mode != "head":
            return (self._reject(command, RejectionCode.UNKNOWN_MODE, now_ns),)
        self._accept(command, now_ns)
        return ()

    def _handle_recenter(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, PosePayload)
        if self.state not in {GatewayState.AWAITING_RECENTER, GatewayState.HEAD_ACTIVE}:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        was_active = self.state is GatewayState.HEAD_ACTIVE
        self.neck_controller.recenter(
            command.payload.orientation.normalized(),
            now_ns,
            preserve_target=was_active,
        )
        self._accept(command, now_ns)
        transition = self._transition(
            GatewayState.HEAD_ACTIVE,
            command.session_id,
            command.sequence,
            now_ns,
        )
        return (transition,) if transition is not None else ()

    def _handle_pose(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, PosePayload)
        if self.state is not GatewayState.HEAD_ACTIVE:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        target = self.neck_controller.update(
            command.payload.orientation.normalized(),
            now_ns,
        )
        self._accept(command, now_ns)
        return (
            NeckTargetEvent(
                now_ns,
                command.session_id,
                command.sequence,
                target.pan_degrees,
                target.tilt_degrees,
            ),
        )

    def _handle_session_stop(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        self._accept(command, now_ns)
        transition = self._transition(
            GatewayState.IDLE,
            command.session_id,
            command.sequence,
            now_ns,
        )
        stop = SafetyStopEvent(
            now_ns,
            StopReason.SESSION_STOPPED,
            command.session_id,
            command.sequence,
        )
        self._invalidate_active_session()
        events: list[OutputEvent] = []
        if transition is not None:
            events.append(transition)
        events.append(stop)
        return tuple(events)

    def _handle_emergency_stop(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        transition = self._transition(
            GatewayState.ESTOP_LATCHED,
            command.session_id,
            command.sequence,
            now_ns,
        )
        self._invalidate_active_session()
        stop = SafetyStopEvent(
            now_ns,
            StopReason.EMERGENCY_STOP,
            command.session_id,
            command.sequence,
        )
        if transition is None:
            return (stop,)
        return transition, stop

    def _accept(self, command: CommandEnvelope, now_ns: int) -> None:
        self.last_sequence = command.sequence
        self.last_timestamp_ms = command.timestamp_ms
        self.last_valid_packet_received_monotonic_ns = now_ns

    def _invalidate_active_session(self) -> None:
        self.active_session_id = None
        self.last_sequence = None
        self.last_timestamp_ms = None
        self.session_started_monotonic_ns = None
        self.last_valid_packet_received_monotonic_ns = None

    def _transition(
        self,
        state: GatewayState,
        session_id: str | None,
        sequence: int | None,
        now_ns: int,
    ) -> GatewayStateEvent | None:
        if self.state is state:
            return None
        self.state = state
        return GatewayStateEvent(now_ns, state, session_id, sequence)

    def _reject(
        self,
        command: CommandEnvelope,
        code: RejectionCode,
        now_ns: int,
    ) -> CommandRejectedEvent:
        return CommandRejectedEvent(
            now_ns,
            code,
            _REJECTION_MESSAGES[code],
            command.session_id,
            command.sequence,
        )

    def _reject_untrusted(
        self,
        command: object,
        code: RejectionCode,
        now_ns: int,
    ) -> CommandRejectedEvent:
        attributes = command.__dict__ if type(command) is CommandEnvelope else {}
        session_id = attributes.get("session_id")
        sequence = attributes.get("sequence")
        if type(session_id) is not str or not session_id:
            session_id = None
        if type(sequence) is not int or sequence < 1:
            sequence = None
        return CommandRejectedEvent(
            now_ns,
            code,
            _REJECTION_MESSAGES[code],
            session_id,
            sequence,
        )
