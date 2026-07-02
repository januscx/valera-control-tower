from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from robot.adapters.arm import ArmCommandResult, ArmProbeResult
from robot.adapters.camera import CameraProbeResult, FrameCaptureResult
from robot.adapters.vision import BoundingBox, VisionDetection, VisionResult
from robot.events import EventEnvelope, EventError, EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError, Zone
from robot.state_machine import TaskEventLog


ADAPTER_SIM_TIMESTAMP_BASE = datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc)
ADAPTER_SIM_SOURCE = "valera.adapter_sim_mission"


def run_adapter_simulated_mission(
    *,
    task: Task,
    camera: Any,
    vision: Any,
    arm: Any,
) -> TaskEventLog:
    if task.mode != ExecutionMode.SIMULATION:
        raise ValidationError("adapter simulator only accepts simulation tasks", FailureCode.INVALID_TASK)

    builder = _EventBuilder(task)
    builder.append(EventType.TASK_CREATED, _base_payload(task) | {"status": "created"})
    builder.append(
        EventType.PLAN_CREATED,
        _base_payload(task)
        | {
            "status": "planned",
            "planned_route": [
                Zone.BASE.value,
                task.pickup_zone.value,
                task.delivery_zone.value,
            ],
        },
    )
    builder.append(EventType.TASK_ACCEPTED, _base_payload(task) | {"status": "accepted"})
    builder.append(
        EventType.ROUTE_STARTED,
        _base_payload(task) | {"status": "in_transit", "current_target_zone": task.pickup_zone.value},
    )
    builder.append(
        EventType.ROUTE_ARRIVED,
        _base_payload(task) | {"status": "arrived", "current_target_zone": task.pickup_zone.value},
    )
    builder.append(
        EventType.OBJECT_SEARCH_STARTED,
        _base_payload(task) | {"status": "searching", "current_target_zone": task.pickup_zone.value},
    )

    camera_probe = camera.probe()
    builder.append(EventType.CAMERA_PROBE_COMPLETED, _camera_probe_payload(task, camera_probe))

    frame = camera.capture_frame()
    builder.append(EventType.CAMERA_FRAME_CAPTURED, _frame_payload(task, frame))

    if frame.artifact is None:
        builder.fail(FailureCode.OBJECT_NOT_FOUND, "simulated camera did not return a frame")
        return builder.event_log

    vision_result = vision.detect(frame.artifact.artifact_uri)
    if not vision_result.detections:
        builder.append(
            EventType.OBJECT_NOT_FOUND,
            _base_payload(task)
            | {
                "status": "not_found",
                "source_artifact_uri": vision_result.source_artifact_uri,
                "adapter_id": vision_result.identity.adapter_id,
                "adapter_mode": vision_result.identity.mode.value,
            },
        )
        builder.fail(FailureCode.OBJECT_NOT_FOUND, "vision adapter returned no detections")
        return builder.event_log

    builder.append(EventType.VISION_OBJECT_DETECTED, _vision_payload(task, vision_result))
    builder.append(
        EventType.OBJECT_FOUND,
        _base_payload(task)
        | {
            "status": "found",
            "current_target_zone": task.pickup_zone.value,
            "object_id": vision_result.detections[0].object_id,
            "label": vision_result.detections[0].label,
            "confidence": vision_result.detections[0].confidence,
            "source_artifact_uri": vision_result.source_artifact_uri,
        },
    )

    arm_probe = arm.probe()
    builder.append(EventType.HARDWARE_PROBE_COMPLETED, _arm_probe_payload(task, arm_probe))
    builder.append(
        EventType.GRASP_STARTED,
        _base_payload(task) | {"status": "grasping", "current_target_zone": task.pickup_zone.value},
    )
    grasp = arm.simulate_grasp(gripper_open=False)
    builder.append(EventType.OBJECT_GRASPED, _grasp_payload(task, grasp))

    builder.append(
        EventType.DELIVERY_STARTED,
        _base_payload(task) | {"status": "delivering", "current_target_zone": task.delivery_zone.value},
    )
    builder.append(
        EventType.ROUTE_ARRIVED,
        _base_payload(task) | {"status": "arrived", "current_target_zone": task.delivery_zone.value},
    )
    builder.append(
        EventType.OBJECT_RELEASED,
        _base_payload(task) | {"status": "released", "current_target_zone": task.delivery_zone.value},
    )
    builder.append(
        EventType.DELIVERY_COMPLETED,
        _base_payload(task) | {"status": "delivered", "current_target_zone": task.delivery_zone.value},
    )
    builder.append(
        EventType.TASK_COMPLETED,
        _base_payload(task) | {"status": "completed", "current_target_zone": task.delivery_zone.value},
    )
    builder.event_log.validate()
    return builder.event_log


class _EventBuilder:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.correlation_id = f"{task.task_id}-adapter-simulation"
        self.event_log = TaskEventLog(task.task_id)

    def append(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        *,
        error: EventError | None = None,
    ) -> None:
        sequence = self.event_log.last_sequence + 1
        self.event_log.append(
            EventEnvelope(
                event_id=f"{self.correlation_id}-{sequence:03d}",
                task_id=self.task.task_id,
                correlation_id=self.correlation_id,
                sequence=sequence,
                event_type=event_type,
                occurred_at=ADAPTER_SIM_TIMESTAMP_BASE + timedelta(seconds=sequence - 1),
                source=ADAPTER_SIM_SOURCE,
                mode=ExecutionMode.SIMULATION,
                payload=payload,
                error=error,
            )
        )

    def fail(self, code: FailureCode, message: str) -> None:
        self.append(
            EventType.TASK_FAILED,
            _base_payload(self.task) | {"status": "failed"},
            error=EventError(code=code, message=message),
        )
        self.event_log.validate()


def _base_payload(task: Task) -> dict[str, Any]:
    return {
        "object_id": task.object_id,
        "pickup_zone": task.pickup_zone.value,
        "delivery_zone": task.delivery_zone.value,
    }


def _camera_probe_payload(task: Task, probe: CameraProbeResult) -> dict[str, Any]:
    role = probe.capabilities.roles[0].value if probe.capabilities.roles else ""
    return _base_payload(task) | {
        "status": "camera_ready" if probe.ok else "camera_unavailable",
        "adapter_id": probe.identity.adapter_id,
        "adapter_mode": probe.identity.mode.value,
        "adapter_type": probe.identity.adapter_type.value,
        "camera_role": role,
        "device_label": probe.device_label,
        "supports_frame_capture": probe.capabilities.supports_frame_capture,
        "supports_depth": probe.capabilities.supports_depth,
    }


def _frame_payload(task: Task, frame: FrameCaptureResult) -> dict[str, Any]:
    payload = _base_payload(task) | {
        "status": "captured" if frame.ok else "capture_failed",
        "adapter_id": frame.identity.adapter_id,
        "adapter_mode": frame.identity.mode.value,
        "adapter_type": frame.identity.adapter_type.value,
        "camera_role": frame.camera_role.value,
    }
    if frame.artifact is not None:
        payload |= {
            "artifact_uri": frame.artifact.artifact_uri,
            "frame_hash": frame.artifact.frame_hash,
            "media_type": frame.artifact.media_type,
            "width": frame.artifact.width,
            "height": frame.artifact.height,
        }
    return payload


def _vision_payload(task: Task, result: VisionResult) -> dict[str, Any]:
    return _base_payload(task) | {
        "status": "detected",
        "adapter_id": result.identity.adapter_id,
        "adapter_mode": result.identity.mode.value,
        "adapter_type": result.identity.adapter_type.value,
        "source_artifact_uri": result.source_artifact_uri,
        "detections": [_detection_to_dict(detection) for detection in result.detections],
    }


def _arm_probe_payload(task: Task, probe: ArmProbeResult) -> dict[str, Any]:
    return _base_payload(task) | {
        "status": "arm_ready" if probe.ok else "arm_unavailable",
        "adapter_id": probe.identity.adapter_id,
        "adapter_mode": probe.identity.mode.value,
        "adapter_type": probe.identity.adapter_type.value,
        "can_read_state": probe.capabilities.can_read_state,
        "can_enable_torque": probe.capabilities.can_enable_torque,
        "can_move": probe.capabilities.can_move,
        "joint_count": probe.capabilities.joint_count,
        "runtime": probe.runtime,
    }


def _grasp_payload(task: Task, result: ArmCommandResult) -> dict[str, Any]:
    return _base_payload(task) | {
        "status": "secured" if result.ok and result.executed else "grasp_failed",
        "adapter_id": result.identity.adapter_id,
        "adapter_mode": result.identity.mode.value,
        "adapter_type": result.identity.adapter_type.value,
        "command_name": result.command_name,
        "executed": result.executed,
        "torque_enabled": result.state.torque_enabled if result.state is not None else None,
        "current_target_zone": task.pickup_zone.value,
    }


def _detection_to_dict(detection: VisionDetection) -> dict[str, Any]:
    data: dict[str, Any] = {
        "object_id": detection.object_id,
        "label": detection.label,
        "confidence": detection.confidence,
        "metadata": detection.metadata,
    }
    if detection.bounding_box is not None:
        data["bounding_box"] = _bounding_box_to_dict(detection.bounding_box)
    return data


def _bounding_box_to_dict(bounding_box: BoundingBox) -> dict[str, int]:
    return {
        "x": bounding_box.x,
        "y": bounding_box.y,
        "width": bounding_box.width,
        "height": bounding_box.height,
    }
