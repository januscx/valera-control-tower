import pytest

from robot.vr_gateway.gateway import GatewayConfig, VrGateway
from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    EmptyPayload,
    GatewayState,
    GatewayStateEvent,
    ModeSetPayload,
    NeckTargetEvent,
    PosePayload,
    Quaternion,
    RejectionCode,
    SafetyStopEvent,
    SessionStartPayload,
    StopReason,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController


class FakeClock:
    def __init__(self):
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns

    def advance_ms(self, value: int) -> None:
        self.now_ns += value * 1_000_000


def neck_controller() -> NeckController:
    return NeckController(
        NeckControlConfig(
            center_pan_degrees=0.0,
            center_tilt_degrees=0.0,
            initial_pan_degrees=0.0,
            initial_tilt_degrees=0.0,
            pan_gain=1.0,
            tilt_gain=1.0,
            filter_time_constant_seconds=0.0,
            max_pan_rate_degrees_per_second=1_000.0,
            max_tilt_rate_degrees_per_second=1_000.0,
            min_pan_degrees=-180.0,
            max_pan_degrees=180.0,
            min_tilt_degrees=-90.0,
            max_tilt_degrees=90.0,
        )
    )


def make_gateway() -> tuple[VrGateway, FakeClock]:
    clock = FakeClock()
    return VrGateway(neck_controller(), clock=clock), clock


def command(
    name: CommandName,
    payload,
    *,
    session_id: str = "session-a",
    sequence: int = 1,
    timestamp_ms: int = 0,
) -> CommandEnvelope:
    return CommandEnvelope("0.1", name, session_id, sequence, timestamp_ms, payload)


def start(
    gateway: VrGateway,
    *,
    session_id: str = "session-a",
    sequence: int = 1,
    requested_mode: str = "head",
) -> tuple:
    return gateway.handle(
        command(
            CommandName.SESSION_START,
            SessionStartPayload(requested_mode),
            session_id=session_id,
            sequence=sequence,
        )
    )


def recenter(
    gateway: VrGateway,
    *,
    session_id: str = "session-a",
    sequence: int = 2,
    timestamp_ms: int = 1,
    orientation: Quaternion = Quaternion(0.0, 0.0, 0.0, 1.0),
) -> tuple:
    return gateway.handle(
        command(
            CommandName.HEAD_RECENTER,
            PosePayload("quest_local", orientation),
            session_id=session_id,
            sequence=sequence,
            timestamp_ms=timestamp_ms,
        )
    )


def rejection(events: tuple) -> CommandRejectedEvent:
    assert len(events) == 1
    assert isinstance(events[0], CommandRejectedEvent)
    return events[0]


def test_config_has_safety_timer_defaults():
    assert GatewayConfig() == GatewayConfig(
        handshake_timeout_ns=10_000_000_000,
        motion_watchdog_timeout_ns=250_000_000,
    )


def test_session_start_requires_sequence_one_and_enters_awaiting_recenter():
    gateway, _ = make_gateway()

    invalid = rejection(start(gateway, sequence=2))
    events = start(gateway)

    assert invalid.code is RejectionCode.INVALID_PAYLOAD
    assert events == (
        GatewayStateEvent(0, GatewayState.AWAITING_RECENTER, "session-a", 1),
    )
    assert gateway.state is GatewayState.AWAITING_RECENTER


def test_session_start_routes_unknown_mode_and_rejects_reused_id():
    gateway, _ = make_gateway()

    unknown = rejection(start(gateway, requested_mode="banana"))
    start(gateway)
    reused = rejection(start(gateway))

    assert unknown.code is RejectionCode.UNKNOWN_MODE
    assert reused.code is RejectionCode.INVALID_PAYLOAD


def test_new_session_invalidates_previous_session():
    gateway, _ = make_gateway()
    start(gateway)
    recenter(gateway)

    events = start(gateway, session_id="session-b")
    old_session = rejection(
        recenter(gateway, session_id="session-a", sequence=3, timestamp_ms=2)
    )

    assert events == (
        GatewayStateEvent(0, GatewayState.AWAITING_RECENTER, "session-b", 1),
    )
    assert old_session.code is RejectionCode.SESSION_MISMATCH


def test_missing_and_mismatched_sessions_have_distinct_rejections():
    gateway, _ = make_gateway()
    missing = rejection(
        gateway.handle(command(CommandName.MODE_SET, ModeSetPayload("head")))
    )
    start(gateway)
    mismatch = rejection(
        gateway.handle(
            command(
                CommandName.MODE_SET,
                ModeSetPayload("head"),
                session_id="session-b",
                sequence=2,
            )
        )
    )

    assert missing.code is RejectionCode.NO_ACTIVE_SESSION
    assert mismatch.code is RejectionCode.SESSION_MISMATCH


def test_equal_timestamp_with_higher_sequence_is_accepted_without_state_event():
    gateway, _ = make_gateway()
    start(gateway)

    events = gateway.handle(
        command(
            CommandName.MODE_SET,
            ModeSetPayload("head"),
            sequence=2,
            timestamp_ms=0,
        )
    )

    assert events == ()


def test_ordering_rejects_timestamp_regression_and_nonincreasing_sequence():
    gateway, _ = make_gateway()
    start(gateway)
    gateway.handle(
        command(
            CommandName.MODE_SET,
            ModeSetPayload("head"),
            sequence=3,
            timestamp_ms=10,
        )
    )

    stale_timestamp = rejection(
        gateway.handle(
            command(
                CommandName.MODE_SET,
                ModeSetPayload("head"),
                sequence=4,
                timestamp_ms=9,
            )
        )
    )
    stale_sequence = rejection(
        gateway.handle(
            command(
                CommandName.MODE_SET,
                ModeSetPayload("head"),
                sequence=3,
                timestamp_ms=11,
            )
        )
    )

    assert stale_timestamp.code is RejectionCode.STALE_TIMESTAMP
    assert stale_sequence.code is RejectionCode.STALE_SEQUENCE


def test_wrong_payload_is_rejected_with_bounded_static_message():
    gateway, _ = make_gateway()
    start(gateway)
    secret = "private-payload-data"

    event = rejection(
        gateway.handle(
            command(
                CommandName.SESSION_STOP,
                ModeSetPayload(secret),
                sequence=2,
            )
        )
    )

    assert event.code is RejectionCode.INVALID_PAYLOAD
    assert secret not in event.message
    assert len(event.message) <= 80


def test_head_only_mode_routing_distinguishes_blocked_and_unknown_modes():
    gateway, _ = make_gateway()
    start(gateway)

    drive = rejection(
        gateway.handle(
            command(CommandName.MODE_SET, ModeSetPayload("drive"), sequence=2)
        )
    )
    arm = rejection(
        gateway.handle(
            command(CommandName.MODE_SET, ModeSetPayload("arm"), sequence=2)
        )
    )
    banana = rejection(
        gateway.handle(
            command(CommandName.MODE_SET, ModeSetPayload("banana"), sequence=2)
        )
    )

    assert drive.code is RejectionCode.MODE_BLOCKED
    assert arm.code is RejectionCode.MODE_BLOCKED
    assert banana.code is RejectionCode.UNKNOWN_MODE


def test_first_recenter_enters_head_active_without_neck_target():
    gateway, _ = make_gateway()
    start(gateway)

    events = recenter(gateway, orientation=Quaternion(0.0, 0.0, 0.0, 2.0))

    assert events == (
        GatewayStateEvent(0, GatewayState.HEAD_ACTIVE, "session-a", 2),
    )
    assert not any(isinstance(event, NeckTargetEvent) for event in events)


def test_active_recenter_preserves_last_target_and_emits_nothing():
    gateway, clock = make_gateway()
    start(gateway)
    recenter(gateway)
    clock.advance_ms(100)
    pose_events = gateway.handle(
        command(
            CommandName.HEAD_POSE,
            PosePayload("quest_local", Quaternion(0.0, 0.1, 0.0, 1.0)),
            sequence=3,
            timestamp_ms=2,
        )
    )
    target = pose_events[0]

    events = recenter(
        gateway,
        sequence=4,
        timestamp_ms=3,
        orientation=Quaternion(0.0, 0.2, 0.0, 2.0),
    )

    assert isinstance(target, NeckTargetEvent)
    assert events == ()
    assert gateway.neck_controller.last_target.pan_degrees == target.pan_degrees
    assert gateway.neck_controller.last_target.tilt_degrees == target.tilt_degrees


def test_gateway_normalizes_every_orientation_before_controller_call():
    class RecordingController:
        def __init__(self):
            self.orientations = []
            self.last_target = type("Target", (), {"pan_degrees": 1.0, "tilt_degrees": 2.0})()

        def recenter(self, orientation, now_ns, preserve_target=False):
            self.orientations.append(orientation)

        def update(self, orientation, now_ns):
            self.orientations.append(orientation)
            return self.last_target

    controller = RecordingController()
    clock = FakeClock()
    gateway = VrGateway(controller, clock=clock)
    start(gateway)
    recenter(gateway, orientation=Quaternion(0.0, 0.0, 0.0, 2.0))
    gateway.handle(
        command(
            CommandName.HEAD_POSE,
            PosePayload("quest_local", Quaternion(0.0, 2.0, 0.0, 2.0)),
            sequence=3,
            timestamp_ms=2,
        )
    )

    assert all(value.norm == pytest.approx(1.0) for value in controller.orientations)


def test_session_stop_enters_idle_and_emits_safe_hold_actions():
    gateway, _ = make_gateway()
    start(gateway)
    recenter(gateway)

    events = gateway.handle(
        command(CommandName.SESSION_STOP, EmptyPayload(), sequence=3, timestamp_ms=2)
    )

    assert events == (
        GatewayStateEvent(0, GatewayState.IDLE, "session-a", 3),
        SafetyStopEvent(0, StopReason.SESSION_STOPPED, "session-a", 3),
    )
    assert events[1].neck_action == "HOLD_LAST_POSITION"
    assert events[1].base_action == "STOP"
    assert events[1].arm_action == "HOLD"


def test_handshake_timeout_returns_to_idle_without_safety_stop():
    gateway, clock = make_gateway()
    start(gateway)
    clock.advance_ms(9_999)
    assert gateway.poll() == ()

    clock.advance_ms(1)
    events = gateway.poll()

    assert events == (
        GatewayStateEvent(
            10_000_000_000,
            GatewayState.IDLE,
            "session-a",
            1,
        ),
    )
    assert not any(isinstance(event, SafetyStopEvent) for event in events)
    assert gateway.poll() == ()
