from robot.adapters.base import (
    AdapterFailure,
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterResult,
    AdapterStatus,
    AdapterType,
)


def test_common_adapter_models_are_explicit_and_structured():
    identity = AdapterIdentity(
        adapter_id="sim-arm-001",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.SIMULATION,
        display_name="Simulated arm",
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="ready")
    failure = AdapterFailure(code="adapter.timeout", message="probe timed out")
    result = AdapterResult(ok=False, identity=identity, health=health, failure=failure)

    assert identity.adapter_type == AdapterType.ARM
    assert identity.mode == AdapterMode.SIMULATION
    assert health.status == AdapterStatus.OK
    assert result.ok is False
    assert result.failure.code == "adapter.timeout"
