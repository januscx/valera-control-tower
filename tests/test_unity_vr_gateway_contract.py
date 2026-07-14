from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    ModeSetPayload,
    RejectionCode,
    SessionStartPayload,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController


def test_unknown_unity_mode_is_rejected_by_the_python_gateway():
    gateway = VrGateway(
        NeckController(
            NeckControlConfig(0, 0, 0, 0, 1, 1, 0, 10, 10, -10, 10, -10, 10)
        ),
        clock=lambda: 0,
    )
    gateway.handle(
        CommandEnvelope("0.1", CommandName.SESSION_START, "unity-session", 1, 0, SessionStartPayload("head"))
    )

    events = gateway.handle(
        CommandEnvelope("0.1", CommandName.MODE_SET, "unity-session", 2, 1, ModeSetPayload("inspection"))
    )

    assert events[0].code is RejectionCode.UNKNOWN_MODE
