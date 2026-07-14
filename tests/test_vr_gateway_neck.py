import math

import pytest

from robot.vr_gateway.messages import Quaternion
from robot.vr_gateway.neck import NeckControlConfig, NeckController, NeckTarget


def axis_angle(axis: str, degrees: float) -> Quaternion:
    half_angle = math.radians(degrees) / 2.0
    component = math.sin(half_angle)
    values = {"x": 0.0, "y": 0.0, "z": 0.0}
    values[axis] = component
    return Quaternion(values["x"], values["y"], values["z"], math.cos(half_angle))


def config(**overrides: float) -> NeckControlConfig:
    values = {
        "center_pan_degrees": 0.0,
        "center_tilt_degrees": 0.0,
        "initial_pan_degrees": 0.0,
        "initial_tilt_degrees": 0.0,
        "pan_gain": 1.0,
        "tilt_gain": 1.0,
        "filter_time_constant_seconds": 0.0,
        "max_pan_rate_degrees_per_second": 1_000.0,
        "max_tilt_rate_degrees_per_second": 1_000.0,
        "min_pan_degrees": -180.0,
        "max_pan_degrees": 180.0,
        "min_tilt_degrees": -90.0,
        "max_tilt_degrees": 90.0,
    }
    values.update(overrides)
    return NeckControlConfig(**values)


@pytest.mark.parametrize(
    ("orientation", "expected"),
    [
        (Quaternion(0.0, 0.0, 0.0, 1.0), NeckTarget(0.0, 0.0)),
        (axis_angle("y", 30.0), NeckTarget(30.0, 0.0)),
        (axis_angle("x", 20.0), NeckTarget(0.0, 20.0)),
    ],
)
def test_openxr_orientation_maps_to_signed_pan_and_tilt(orientation, expected):
    controller = NeckController(config())
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=0)

    target = controller.update(orientation, now_ns=1_000_000_000)

    assert target.pan_degrees == pytest.approx(expected.pan_degrees)
    assert target.tilt_degrees == pytest.approx(expected.tilt_degrees)


def test_recenter_makes_subsequent_orientation_relative_and_emits_no_target():
    controller = NeckController(config())

    result = controller.recenter(axis_angle("y", 10.0), now_ns=0)
    target = controller.update(axis_angle("y", 40.0), now_ns=1_000_000_000)

    assert result is None
    assert target.pan_degrees == pytest.approx(30.0)


def test_same_orientation_after_recenter_produces_center_target():
    controller = NeckController(config(center_pan_degrees=3.0, center_tilt_degrees=-2.0))
    orientation = axis_angle("y", 25.0)
    controller.recenter(orientation, now_ns=0)

    assert controller.update(orientation, now_ns=1_000_000_000) == NeckTarget(3.0, -2.0)


def test_low_pass_filter_has_deterministic_one_second_response():
    controller = NeckController(config(filter_time_constant_seconds=1.0))
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=0)

    target = controller.update(axis_angle("y", 30.0), now_ns=1_000_000_000)

    assert target.pan_degrees == pytest.approx(30.0 * (1.0 - math.exp(-1.0)))


def test_pan_and_tilt_gains_are_applied_independently():
    controller = NeckController(config(pan_gain=2.0, tilt_gain=0.5))
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=0)

    target = controller.update(
        Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=1_000_000_000
    )
    yaw_target = controller.update(axis_angle("y", 10.0), now_ns=2_000_000_000)

    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=2_000_000_000)
    pitch_target = controller.update(axis_angle("x", 20.0), now_ns=3_000_000_000)

    assert target == NeckTarget(0.0, 0.0)
    assert yaw_target.pan_degrees == pytest.approx(20.0)
    assert pitch_target.tilt_degrees == pytest.approx(10.0)


def test_rate_limits_pan_and_tilt_independently():
    controller = NeckController(
        config(
            max_pan_rate_degrees_per_second=5.0,
            max_tilt_rate_degrees_per_second=8.0,
        )
    )
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=0)

    pan = controller.update(axis_angle("y", 30.0), now_ns=500_000_000)
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=500_000_000)
    tilt = controller.update(axis_angle("x", -30.0), now_ns=1_000_000_000)

    assert pan.pan_degrees == pytest.approx(2.5)
    assert tilt.tilt_degrees == pytest.approx(-4.0)


def test_mechanical_intervals_clamp_targets():
    controller = NeckController(
        config(
            min_pan_degrees=-10.0,
            max_pan_degrees=12.0,
            min_tilt_degrees=-6.0,
            max_tilt_degrees=7.0,
        )
    )
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=0)

    pan = controller.update(axis_angle("y", 30.0), now_ns=1_000_000_000)
    controller.recenter(Quaternion(0.0, 0.0, 0.0, 1.0), now_ns=1_000_000_000)
    tilt = controller.update(axis_angle("x", -20.0), now_ns=2_000_000_000)

    assert pan.pan_degrees == 12.0
    assert tilt.tilt_degrees == -6.0


def test_active_recenter_retains_last_target():
    controller = NeckController(config())
    controller.recenter(axis_angle("y", 10.0), now_ns=0)
    target = controller.update(axis_angle("y", 40.0), now_ns=1_000_000_000)

    controller.recenter(axis_angle("y", 40.0), now_ns=1_000_000_000, preserve_target=True)

    assert controller.last_target == target
    retained = controller.update(axis_angle("y", 40.0), now_ns=2_000_000_000)
    assert retained.pan_degrees == pytest.approx(target.pan_degrees)


@pytest.mark.parametrize(
    "overrides",
    [
        {"pan_gain": math.inf},
        {"filter_time_constant_seconds": -0.1},
        {"max_pan_rate_degrees_per_second": 0.0},
        {"max_tilt_rate_degrees_per_second": -1.0},
        {"initial_pan_degrees": 181.0},
        {"initial_tilt_degrees": -91.0},
        {"min_pan_degrees": 2.0, "max_pan_degrees": 1.0},
        {"min_tilt_degrees": 2.0, "max_tilt_degrees": 1.0},
    ],
)
def test_config_rejects_unsafe_values(overrides):
    with pytest.raises(ValueError):
        config(**overrides)
