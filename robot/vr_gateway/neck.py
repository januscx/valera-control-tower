from __future__ import annotations

from dataclasses import dataclass, fields
from math import atan2, degrees, exp, hypot, isfinite

from robot.vr_gateway.messages import Quaternion


@dataclass(frozen=True)
class NeckControlConfig:
    center_pan_degrees: float
    center_tilt_degrees: float
    initial_pan_degrees: float
    initial_tilt_degrees: float
    pan_gain: float
    tilt_gain: float
    filter_time_constant_seconds: float
    max_pan_rate_degrees_per_second: float
    max_tilt_rate_degrees_per_second: float
    min_pan_degrees: float
    max_pan_degrees: float
    min_tilt_degrees: float
    max_tilt_degrees: float

    def __post_init__(self) -> None:
        if not all(isfinite(getattr(self, field.name)) for field in fields(self)):
            raise ValueError("neck control configuration values must be finite")
        if self.min_pan_degrees > self.max_pan_degrees:
            raise ValueError("minimum pan must not exceed maximum pan")
        if self.min_tilt_degrees > self.max_tilt_degrees:
            raise ValueError("minimum tilt must not exceed maximum tilt")
        if self.filter_time_constant_seconds < 0.0:
            raise ValueError("filter time constant must be non-negative")
        if self.max_pan_rate_degrees_per_second <= 0.0:
            raise ValueError("maximum pan rate must be positive")
        if self.max_tilt_rate_degrees_per_second <= 0.0:
            raise ValueError("maximum tilt rate must be positive")


@dataclass(frozen=True)
class NeckTarget:
    pan_degrees: float
    tilt_degrees: float


class NeckController:
    def __init__(self, config: NeckControlConfig):
        self._config = config
        self._reference = Quaternion(0.0, 0.0, 0.0, 1.0)
        self._base_pan_degrees = config.center_pan_degrees
        self._base_tilt_degrees = config.center_tilt_degrees
        self._filtered_yaw_degrees = 0.0
        self._filtered_pitch_degrees = 0.0
        self._last_update_ns = 0
        self._last_target = NeckTarget(
            config.initial_pan_degrees,
            config.initial_tilt_degrees,
        )

    @property
    def last_target(self) -> NeckTarget:
        return self._last_target

    def recenter(
        self,
        orientation: Quaternion,
        now_ns: int,
        preserve_target: bool = False,
    ) -> None:
        self._reference = orientation
        self._filtered_yaw_degrees = 0.0
        self._filtered_pitch_degrees = 0.0
        self._last_update_ns = now_ns
        if preserve_target:
            self._base_pan_degrees = self._last_target.pan_degrees
            self._base_tilt_degrees = self._last_target.tilt_degrees
        else:
            self._base_pan_degrees = self._config.center_pan_degrees
            self._base_tilt_degrees = self._config.center_tilt_degrees
            self._last_target = NeckTarget(
                self._config.initial_pan_degrees,
                self._config.initial_tilt_degrees,
            )

    def update(self, orientation: Quaternion, now_ns: int) -> NeckTarget:
        dt_seconds = max(0.0, (now_ns - self._last_update_ns) / 1_000_000_000.0)
        self._last_update_ns = now_ns

        yaw_degrees, pitch_degrees = _relative_angles_degrees(
            self._reference,
            orientation,
        )
        alpha = _filter_alpha(dt_seconds, self._config.filter_time_constant_seconds)
        self._filtered_yaw_degrees += alpha * (yaw_degrees - self._filtered_yaw_degrees)
        self._filtered_pitch_degrees += alpha * (pitch_degrees - self._filtered_pitch_degrees)

        requested_pan = (
            self._base_pan_degrees
            + self._config.pan_gain * self._filtered_yaw_degrees
        )
        requested_tilt = (
            self._base_tilt_degrees
            + self._config.tilt_gain * self._filtered_pitch_degrees
        )

        pan = _rate_limit(
            requested_pan,
            self._last_target.pan_degrees,
            self._config.max_pan_rate_degrees_per_second * dt_seconds,
        )
        tilt = _rate_limit(
            requested_tilt,
            self._last_target.tilt_degrees,
            self._config.max_tilt_rate_degrees_per_second * dt_seconds,
        )
        self._last_target = NeckTarget(
            _clamp(pan, self._config.min_pan_degrees, self._config.max_pan_degrees),
            _clamp(tilt, self._config.min_tilt_degrees, self._config.max_tilt_degrees),
        )
        return self._last_target


def _filter_alpha(dt_seconds: float, time_constant_seconds: float) -> float:
    if time_constant_seconds == 0.0:
        return 1.0
    return 1.0 - exp(-dt_seconds / time_constant_seconds)


def _relative_angles_degrees(
    reference: Quaternion,
    orientation: Quaternion,
) -> tuple[float, float]:
    relative = _multiply(_inverse(reference), orientation)
    forward_x, forward_y, forward_z = _rotate_forward(relative)
    yaw_radians = atan2(-forward_x, -forward_z)
    pitch_radians = atan2(forward_y, hypot(forward_x, forward_z))
    return degrees(yaw_radians), degrees(pitch_radians)


def _inverse(value: Quaternion) -> Quaternion:
    norm_squared = (
        value.x * value.x
        + value.y * value.y
        + value.z * value.z
        + value.w * value.w
    )
    return Quaternion(
        -value.x / norm_squared,
        -value.y / norm_squared,
        -value.z / norm_squared,
        value.w / norm_squared,
    )


def _multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    return Quaternion(
        left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
        left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
        left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
        left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z,
    )


def _rotate_forward(value: Quaternion) -> tuple[float, float, float]:
    rotated = _multiply(
        _multiply(value, Quaternion(0.0, 0.0, -1.0, 0.0)),
        _inverse(value),
    )
    return rotated.x, rotated.y, rotated.z


def _rate_limit(requested: float, previous: float, maximum_delta: float) -> float:
    return _clamp(requested, previous - maximum_delta, previous + maximum_delta)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
