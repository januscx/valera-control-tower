"""SO-ARM identity protocol planning and explicitly confirmed probing.

The functions in this module model a non-actuating Feetech-style PING request.
They do not import LeRobot and they do not expose torque, homing, calibration,
or motion operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SAFETY_FLAGS_FALSE = {
    "serial_opened": False,
    "serial_commands_sent": False,
    "torque_enabled": False,
    "movement_commanded": False,
    "actuator_calls": False,
}


@dataclass(frozen=True)
class SOArmProtocolCandidate:
    name: str
    library_candidate: str
    source_note: str
    import_side_effects_known: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "library_candidate": self.library_candidate,
            "source_note": self.source_note,
            "import_side_effects_known": self.import_side_effects_known,
        }


@dataclass(frozen=True)
class SOArmProtocolSafetyAssessment:
    query_is_passive: bool
    query_requires_bytes: bool
    torque_required: bool
    movement_required: bool
    homing_required: bool
    actuator_calls: bool
    execution_approved: bool
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "query_is_passive": self.query_is_passive,
            "query_requires_bytes": self.query_requires_bytes,
            "torque_required": self.torque_required,
            "movement_required": self.movement_required,
            "homing_required": self.homing_required,
            "actuator_calls": self.actuator_calls,
            "execution_approved": self.execution_approved,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class SOArmIdentityQueryRequest:
    query_name: str
    servo_id: int
    baudrate: int
    timeout_seconds: float
    request_bytes: bytes
    response_length: int
    query_is_passive: bool

    @property
    def request_bytes_hex(self) -> str:
        return self.request_bytes.hex(" ")

    def to_dict(self) -> dict[str, object]:
        return {
            "query_name": self.query_name,
            "servo_id": self.servo_id,
            "baudrate": self.baudrate,
            "timeout_seconds": self.timeout_seconds,
            "request_bytes_hex": self.request_bytes_hex,
            "bytes_to_write": len(self.request_bytes),
            "response_length": self.response_length,
            "query_is_passive": self.query_is_passive,
        }


@dataclass(frozen=True)
class SOArmIdentityQueryPlan:
    protocol_candidate: SOArmProtocolCandidate
    request: SOArmIdentityQueryRequest
    safety: SOArmProtocolSafetyAssessment
    execution_approved: bool
    operator_checkpoint_command: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_candidate": self.protocol_candidate.to_dict(),
            "request": self.request.to_dict(),
            "safety": self.safety.to_dict(),
            "execution_approved": self.execution_approved,
            "operator_checkpoint_command": self.operator_checkpoint_command,
        }


@dataclass(frozen=True)
class SOArmIdentityQueryResult:
    exit_code: int
    status: str
    serial_open_attempted: bool
    serial_opened: bool
    serial_closed: bool
    query_attempted: bool
    query_name: str
    query_is_passive: bool
    identity_query_bytes_written: int
    identity_response_bytes_read: int
    state_query_bytes_written: int
    state_response_bytes_read: int
    serial_commands_sent: bool
    identity_detected: bool
    identity_summary: dict[str, object] | None
    state_detected: bool
    state_summary: dict[str, object] | None
    safety_flags: dict[str, bool]
    limitations: list[str]
    error: str | None = None

    @property
    def torque_enabled(self) -> bool:
        return self.safety_flags["torque_enabled"]

    @property
    def movement_commanded(self) -> bool:
        return self.safety_flags["movement_commanded"]

    @property
    def actuator_calls(self) -> bool:
        return self.safety_flags["actuator_calls"]

    def to_dict(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "status": self.status,
            "serial_open_attempted": self.serial_open_attempted,
            "serial_opened": self.serial_opened,
            "serial_closed": self.serial_closed,
            "query_attempted": self.query_attempted,
            "query_name": self.query_name,
            "query_is_passive": self.query_is_passive,
            "identity_query_bytes_written": self.identity_query_bytes_written,
            "identity_response_bytes_read": self.identity_response_bytes_read,
            "state_query_bytes_written": self.state_query_bytes_written,
            "state_response_bytes_read": self.state_response_bytes_read,
            "serial_commands_sent": self.serial_commands_sent,
            "identity_detected": self.identity_detected,
            "identity_summary": self.identity_summary,
            "state_detected": self.state_detected,
            "state_summary": self.state_summary,
            "safety_flags": dict(self.safety_flags),
            "limitations": list(self.limitations),
            "error": self.error,
        }


def _packet_checksum(payload_after_header: bytes) -> int:
    return (~sum(payload_after_header)) & 0xFF


def build_feetech_ping_request(servo_id: int) -> bytes:
    if not 0 <= servo_id <= 253:
        raise ValueError("servo_id must be in Feetech unicast range 0..253")
    body = bytes([servo_id, 0x02, 0x01])
    return b"\xff\xff" + body + bytes([_packet_checksum(body)])


def build_default_identity_query_plan(
    *,
    servo_id: int = 1,
    baudrate: int = 1_000_000,
    timeout_seconds: float = 0.5,
) -> SOArmIdentityQueryPlan:
    request = SOArmIdentityQueryRequest(
        query_name=f"feetech_ping_servo_id_{servo_id}",
        servo_id=servo_id,
        baudrate=baudrate,
        timeout_seconds=timeout_seconds,
        request_bytes=build_feetech_ping_request(servo_id),
        response_length=6,
        query_is_passive=False,
    )
    safety = SOArmProtocolSafetyAssessment(
        query_is_passive=False,
        query_requires_bytes=True,
        torque_required=False,
        movement_required=False,
        homing_required=False,
        actuator_calls=False,
        execution_approved=False,
        limitations=[
            "Feetech PING is request/response, not passive read-only.",
            "This plan does not validate model, state, torque, homing, or motion safety.",
            "The live query must be approved at the operator checkpoint before bytes are sent.",
        ],
    )
    command = (
        ".venv/bin/python scripts/probe_so_arm_readiness.py "
        "--enable-non-actuating-identity-query "
        "--confirm-send-non-actuating-identity-query-bytes "
        f"--identity-servo-id {servo_id} "
        f"--serial-timeout-seconds {timeout_seconds}"
    )
    return SOArmIdentityQueryPlan(
        protocol_candidate=SOArmProtocolCandidate(
            name="Feetech serial bus servo protocol",
            library_candidate="project-owned Feetech PING packet via pyserial",
            source_note=(
                "Feetech/SCS-style packets use 0xff 0xff header, id, length, "
                "instruction, parameters, and one's-complement checksum."
            ),
            import_side_effects_known=True,
        ),
        request=request,
        safety=safety,
        execution_approved=False,
        operator_checkpoint_command=command,
    )


def parse_feetech_status_response(response: bytes, *, expected_servo_id: int) -> SOArmIdentityQueryResult:
    base = _base_result(query_name=f"feetech_ping_servo_id_{expected_servo_id}")
    if not response:
        return _replace_result(
            base,
            status="identity_query_timeout",
            identity_response_bytes_read=0,
            error="no response bytes received before timeout",
        )
    if len(response) < 6 or response[:2] != b"\xff\xff":
        return _replace_result(
            base,
            status="identity_query_unexpected_response",
            identity_response_bytes_read=len(response),
            error="response is not a Feetech status packet",
        )

    servo_id = response[2]
    length = response[3]
    packet_end = 4 + length
    if len(response) < packet_end or packet_end < 6:
        return _replace_result(
            base,
            status="identity_query_unexpected_response",
            identity_response_bytes_read=len(response),
            error="response length does not match packet length field",
        )
    packet = response[:packet_end]
    checksum = packet[-1]
    checksum_body = packet[2:-1]
    if checksum != _packet_checksum(checksum_body):
        return _replace_result(
            base,
            status="identity_query_unexpected_response",
            identity_response_bytes_read=len(response),
            error="response checksum mismatch",
        )
    if servo_id != expected_servo_id:
        return _replace_result(
            base,
            status="identity_query_unexpected_response",
            identity_response_bytes_read=len(response),
            error=f"expected servo id {expected_servo_id}, got {servo_id}",
        )
    status_error = packet[4]
    return _replace_result(
        base,
        exit_code=0,
        status="identity_query_response_valid",
        identity_response_bytes_read=len(packet),
        identity_detected=True,
        identity_summary={"servo_id": servo_id, "status_error": status_error},
    )


def execute_confirmed_identity_query(
    plan: SOArmIdentityQueryPlan,
    *,
    device_path: str,
    serial_factory,
    execution_approved: bool,
) -> SOArmIdentityQueryResult:
    if not execution_approved:
        return _base_result(
            query_name=plan.request.query_name,
            status="identity_query_approval_required",
        )

    serial_handle: Any | None = None
    serial_opened = False
    serial_closed = False
    bytes_written = 0
    response = b""
    try:
        serial_handle = serial_factory(
            port=device_path,
            baudrate=plan.request.baudrate,
            timeout=plan.request.timeout_seconds,
            write_timeout=plan.request.timeout_seconds,
        )
        serial_opened = True
        bytes_written = serial_handle.write(plan.request.request_bytes)
        response = serial_handle.read(plan.request.response_length)
    except Exception as exc:
        return _replace_result(
            _base_result(query_name=plan.request.query_name),
            status="identity_query_failed",
            serial_open_attempted=True,
            serial_opened=serial_opened,
            serial_closed=serial_closed,
            query_attempted=serial_opened,
            identity_query_bytes_written=bytes_written,
            identity_response_bytes_read=len(response),
            serial_commands_sent=bytes_written > 0,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if serial_handle is not None:
            try:
                serial_handle.close()
                serial_closed = True
            except Exception:
                serial_closed = False

    parsed = parse_feetech_status_response(response, expected_servo_id=plan.request.servo_id)
    flags = dict(SAFETY_FLAGS_FALSE)
    flags["serial_opened"] = serial_opened
    flags["serial_commands_sent"] = bytes_written > 0
    return _replace_result(
        parsed,
        serial_open_attempted=True,
        serial_opened=serial_opened,
        serial_closed=serial_closed,
        query_attempted=True,
        identity_query_bytes_written=bytes_written,
        identity_response_bytes_read=parsed.identity_response_bytes_read,
        serial_commands_sent=bytes_written > 0,
        safety_flags=flags,
    )


def _base_result(
    *,
    query_name: str,
    status: str = "identity_query_blocked",
) -> SOArmIdentityQueryResult:
    return SOArmIdentityQueryResult(
        exit_code=1,
        status=status,
        serial_open_attempted=False,
        serial_opened=False,
        serial_closed=False,
        query_attempted=False,
        query_name=query_name,
        query_is_passive=False,
        identity_query_bytes_written=0,
        identity_response_bytes_read=0,
        state_query_bytes_written=0,
        state_response_bytes_read=0,
        serial_commands_sent=False,
        identity_detected=False,
        identity_summary=None,
        state_detected=False,
        state_summary=None,
        safety_flags=dict(SAFETY_FLAGS_FALSE),
        limitations=[
            "Non-actuating identity query only; no torque, homing, movement, or state validation.",
            "A successful PING only proves a status packet answered for the requested servo id.",
        ],
    )


def _replace_result(result: SOArmIdentityQueryResult, **changes) -> SOArmIdentityQueryResult:
    values = result.to_dict()
    values.update(changes)
    return SOArmIdentityQueryResult(**values)
