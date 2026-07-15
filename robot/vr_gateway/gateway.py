from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from robot.vr_gateway.messages import (
    ArmJogPayload,
    ArmTargetEvent,
    BaseDrivePayload,
    BaseTargetEvent,
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    ControlMode,
    EmptyPayload,
    GatewayState,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
    ModeTransition,
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
        self.current_mode = ControlMode.HEAD_ONLY
        self.requested_mode: ControlMode | None = None
        self.transition: ModeTransition = ModeTransition.NONE
        self.used_session_ids: set[str] = set()
        self.active_session_id: str | None = None
        self.last_sequence: int | None = None
        self.last_timestamp_ms: int | None = None
        self.session_started_monotonic_ns: int | None = None
        self.last_valid_packet_received_monotonic_ns: int | None = None
        self._brake_dwell_ns: int = 500_000_000
        self._stop_ack_timeout_ns: int = 2_000_000_000
        self._stop_ack_pending: bool = False
        self._stop_ack_deadline_ns: int | None = None
        self._dead_zone: float = 0.1
        self._speed_limit: float = 1.0
        self._slew_rate_limit: float = 10.0
        self._last_throttle: float = 0.0
        self._last_steering: float = 0.0
        self._last_drive_ns: int | None = None

    def handle(self, command: object) -> tuple[OutputEvent, ...]:
        now_ns = self.clock()

        try:
            command = validate_command_envelope(command)
        except (MessageValidationError, AttributeError, TypeError, ValueError):
            deadline_events = self._evaluate_deadline(now_ns)
            return deadline_events + (
                self._reject_untrusted(command, RejectionCode.INVALID_PAYLOAD, now_ns),
            )

        if (
            command.command is CommandName.EMERGENCY_STOP
            and type(command.payload) is EmptyPayload
        ):
            return self._handle_emergency_stop(command, now_ns)

        if (
            command.command is CommandName.EMERGENCY_STOP_RESET
            and type(command.payload) is EmptyPayload
        ):
            return self._handle_estop_reset(command, now_ns)

        deadline_events = self._evaluate_deadline(now_ns)
        if command.command is CommandName.EMERGENCY_STOP:
            return deadline_events + (
                self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),
            )
        if command.command is CommandName.EMERGENCY_STOP_RESET:
            return deadline_events + (
                self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),
            )
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
            CommandName.BASE_DRIVE: BaseDrivePayload,
            CommandName.ARM_JOG: ArmJogPayload,
        }.get(command.command)
        if expected_payload is None or type(command.payload) is not expected_payload:
            return (self._reject(command, RejectionCode.INVALID_PAYLOAD, now_ns),)

        if command.command is CommandName.MODE_SET:
            return self._handle_mode_set(command, now_ns)
        if command.command is CommandName.BASE_DRIVE:
            return self._handle_base_drive(command, now_ns)
        if command.command is CommandName.ARM_JOG:
            return self._handle_arm_jog(command, now_ns)
        if command.command is CommandName.HEAD_RECENTER:
            return self._handle_recenter(command, now_ns)
        if command.command is CommandName.HEAD_POSE:
            return self._handle_pose(command, now_ns)
        return self._handle_session_stop(command, now_ns)

    def poll(self) -> tuple[OutputEvent, ...]:
        now_ns = self.clock()
        return self._evaluate_deadline(now_ns)

    def _evaluate_deadline(self, now_ns: int) -> tuple[OutputEvent, ...]:
        events: list[OutputEvent] = []

        # Handshake timeout
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

        # Brake dwell expired — complete the transition
        if (
            self.transition is ModeTransition.STOPPING_BASE
            and not self._stop_ack_pending
            and self._stop_ack_deadline_ns is not None
            and now_ns >= self._stop_ack_deadline_ns
        ):
            self._stop_ack_deadline_ns = None
            target_mode = self.requested_mode
            self.requested_mode = None
            self.transition = ModeTransition.NONE
            self.current_mode = target_mode
            events.append(
                GatewayStateEvent(
                    now_ns, self.state, self.current_mode,
                    self.active_session_id, self.last_sequence,
                    transition=self.transition,
                )
            )
            return tuple(events)

        # Stop ack timeout — transition fails → SAFE_STOPPED
        if (
            self.transition is ModeTransition.STOPPING_BASE
            and self._stop_ack_pending
            and self._stop_ack_deadline_ns is not None
            and now_ns >= self._stop_ack_deadline_ns
        ):
            self._stop_ack_pending = False
            self._stop_ack_deadline_ns = None
            self.transition = ModeTransition.NONE
            self.requested_mode = None
            ev = self._transition(
                GatewayState.SAFE_STOPPED,
                self.active_session_id,
                self.last_sequence,
                now_ns,
            )
            if ev is not None:
                events.append(ev)
            events.append(
                SafetyStopEvent(
                    now_ns,
                    StopReason.WATCHDOG,
                    self.active_session_id,
                    self.last_sequence,
                )
            )
            return tuple(events)

        # Motion watchdog
        if (
            self.state is GatewayState.ACTIVE
            and self.last_valid_packet_received_monotonic_ns is not None
            and now_ns - self.last_valid_packet_received_monotonic_ns
            >= self.config.motion_watchdog_timeout_ns
        ):
            session_id = self.active_session_id
            sequence = self.last_sequence
            if self.current_mode is ControlMode.DRIVE:
                events.append(
                    BaseTargetEvent(now_ns, 0.0, 0.0, False, True)
                )
            elif self.current_mode is ControlMode.ARM:
                events.append(
                    ArmTargetEvent(now_ns, "JOINT_JOG", False, True, {})
                )
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
            if transition is not None:
                events.append(transition)
            events.append(stop)
            return tuple(events)

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
        if command.payload.requested_mode not in {"head", "drive", "arm"}:
            return (self._reject(command, RejectionCode.UNKNOWN_MODE, now_ns),)

        self.used_session_ids.add(command.session_id)
        self.active_session_id = command.session_id
        self.last_sequence = command.sequence
        self.last_timestamp_ms = command.timestamp_ms
        self.session_started_monotonic_ns = now_ns
        self.last_valid_packet_received_monotonic_ns = now_ns
        self.current_mode = ControlMode.HEAD_ONLY
        self.requested_mode = None
        self.transition = ModeTransition.NONE

        if command.payload.requested_mode != "head":
            self.requested_mode = ControlMode(command.payload.requested_mode.upper())

        self.state = GatewayState.AWAITING_RECENTER
        return (
            GatewayStateEvent(
                now_ns,
                GatewayState.AWAITING_RECENTER,
                self.current_mode,
                command.session_id,
                command.sequence,
                requested_mode=self.requested_mode,
            ),
        )

    def _handle_mode_set(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, ModeSetPayload)
        mode = command.payload.mode

        if mode not in {"head", "drive", "arm"}:
            return (self._reject(command, RejectionCode.UNKNOWN_MODE, now_ns),)

        if self.transition is not ModeTransition.NONE:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)

        if mode == "head":
            return self._handle_mode_set_head(command, now_ns)

        if mode == "drive":
            return self._handle_mode_set_drive(command, now_ns)

        return self._handle_mode_set_arm(command, now_ns)

    def _handle_mode_set_head(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        self.current_mode = ControlMode.HEAD_ONLY
        self.requested_mode = None
        self.transition = ModeTransition.NONE
        self._stop_ack_pending = False
        self._stop_ack_deadline_ns = None
        self._accept(command, now_ns)
        return ()

    def _handle_mode_set_drive(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        if self.current_mode is ControlMode.ARM:
            self.transition = ModeTransition.STOPPING_ARM
            self.requested_mode = ControlMode.DRIVE
            self._accept(command, now_ns)
            return ()
        self.current_mode = ControlMode.DRIVE
        self.requested_mode = None
        self.transition = ModeTransition.NONE
        self._accept(command, now_ns)
        return ()

    def _handle_mode_set_arm(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        if self.current_mode is ControlMode.DRIVE:
            self.transition = ModeTransition.STOPPING_BASE
            self.requested_mode = ControlMode.ARM
            self._stop_ack_pending = True
            self._stop_ack_deadline_ns = now_ns + self._stop_ack_timeout_ns
            self._accept(command, now_ns)
            return (BaseTargetEvent(now_ns, 0.0, 0.0, False, True),)
        self.current_mode = ControlMode.ARM
        self.requested_mode = None
        self.transition = ModeTransition.NONE
        self._accept(command, now_ns)
        return ()

    def _handle_recenter(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, PosePayload)
        if self.state not in {GatewayState.AWAITING_RECENTER, GatewayState.ACTIVE}:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        was_active = self.state is GatewayState.ACTIVE
        self.neck_controller.recenter(
            command.payload.orientation.normalized(),
            now_ns,
            preserve_target=was_active,
        )
        self._accept(command, now_ns)

        mode_changed = False
        if self.requested_mode is not None:
            self.current_mode = self.requested_mode
            self.requested_mode = None
            mode_changed = True

        if not was_active:
            self.state = GatewayState.ACTIVE
            return (
                GatewayStateEvent(
                    now_ns,
                    GatewayState.ACTIVE,
                    self.current_mode,
                    command.session_id,
                    command.sequence,
                    transition=self.transition,
                ),
            )

        if mode_changed:
            return (
                GatewayStateEvent(
                    now_ns,
                    GatewayState.ACTIVE,
                    self.current_mode,
                    command.session_id,
                    command.sequence,
                    transition=self.transition,
                ),
            )
        return ()

    def _handle_pose(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, PosePayload)
        if self.state is not GatewayState.ACTIVE:
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
        self.current_mode = ControlMode.HEAD_ONLY
        self.requested_mode = None
        self.transition = ModeTransition.NONE
        self._stop_ack_pending = False
        self._stop_ack_deadline_ns = None
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

    def _handle_base_drive(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, BaseDrivePayload)
        if self.current_mode is not ControlMode.DRIVE or self.transition is not ModeTransition.NONE:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)

        if not command.payload.deadman:
            self._accept(command, now_ns)
            return (BaseTargetEvent(now_ns, 0.0, 0.0, False, True),)

        throttle, steering = self._apply_throttle_shaping(
            command.payload.throttle, command.payload.steering, now_ns
        )
        self._accept(command, now_ns)
        return (BaseTargetEvent(now_ns, throttle, steering, True, False),)

    def _handle_arm_jog(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        assert isinstance(command.payload, ArmJogPayload)
        if self.current_mode is not ControlMode.ARM or self.transition is not ModeTransition.NONE:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)

        if not command.payload.deadman:
            self._accept(command, now_ns)
            return (ArmTargetEvent(now_ns, "JOINT_JOG", False, True, {}),)

        self._accept(command, now_ns)
        return (
            ArmTargetEvent(
                now_ns, "JOINT_JOG", True, False, command.payload.joint_velocity
            ),
        )

    def _handle_estop_reset(
        self, command: CommandEnvelope, now_ns: int
    ) -> tuple[OutputEvent, ...]:
        if self.state is not GatewayState.ESTOP_LATCHED:
            return (self._reject(command, RejectionCode.MODE_BLOCKED, now_ns),)
        self.current_mode = ControlMode.HEAD_ONLY
        self.requested_mode = None
        self.transition = ModeTransition.NONE
        self._stop_ack_pending = False
        self._stop_ack_deadline_ns = None
        transition = self._transition(
            GatewayState.IDLE, command.session_id, command.sequence, now_ns
        )
        return (transition,) if transition is not None else ()

    def _apply_throttle_shaping(
        self, throttle: float, steering: float, now_ns: int
    ) -> tuple[float, float]:
        if abs(throttle) < self._dead_zone:
            throttle = 0.0
        if abs(steering) < self._dead_zone:
            steering = 0.0

        throttle *= self._speed_limit
        steering *= self._speed_limit

        if self._last_drive_ns is not None:
            dt = (now_ns - self._last_drive_ns) / 1_000_000_000
            if dt > 0:
                max_change = self._slew_rate_limit * dt
                throttle = (
                    max(-max_change, min(max_change, throttle - self._last_throttle))
                    + self._last_throttle
                )
                steering = (
                    max(-max_change, min(max_change, steering - self._last_steering))
                    + self._last_steering
                )

        self._last_throttle = throttle
        self._last_steering = steering
        self._last_drive_ns = now_ns
        return throttle, steering

    def handle_base_stop_ack(
        self, command_zeroed: bool, stationary_verified: bool
    ) -> tuple[OutputEvent, ...]:
        if not command_zeroed:
            return ()
        if self.transition is not ModeTransition.STOPPING_BASE:
            return ()
        self._stop_ack_pending = False
        self._stop_ack_deadline_ns = self.clock() + self._brake_dwell_ns
        return ()

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
        return GatewayStateEvent(
            now_ns,
            state,
            self.current_mode,
            session_id,
            sequence,
            requested_mode=self.requested_mode,
            transition=self.transition,
        )

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
