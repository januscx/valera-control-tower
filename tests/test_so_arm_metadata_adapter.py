from pathlib import Path

from robot.adapters import AdapterMode, AdapterStatus, AdapterType, ArmAdapter, ArmProbeResult
from robot.adapters.so_arm_metadata import MetadataOnlySOArmAdapter


def test_metadata_only_so_arm_adapter_implements_arm_adapter_protocol(tmp_path):
    device = tmp_path / "ttyUSB0"
    device.write_text("", encoding="utf-8")

    adapter: ArmAdapter = MetadataOnlySOArmAdapter(device_path=str(device))

    assert isinstance(adapter, ArmAdapter)
    assert adapter.identity.adapter_id == "metadata-only-so-arm"
    assert adapter.identity.adapter_type == AdapterType.ARM
    assert adapter.identity.mode == AdapterMode.PROBE
    assert adapter.identity.metadata["device_path"] == str(device)


def test_metadata_only_so_arm_adapter_reports_no_hardware_control_capabilities(tmp_path):
    device = tmp_path / "ttyUSB0"
    device.write_text("", encoding="utf-8")
    adapter = MetadataOnlySOArmAdapter(device_path=str(device))

    capabilities = adapter.capabilities()

    assert capabilities.can_read_state is False
    assert capabilities.can_enable_torque is False
    assert capabilities.can_move is False
    assert capabilities.joint_count == 0
    assert capabilities.supported_commands == ("probe_metadata",)
    assert any("does not open serial" in note for note in capabilities.notes)


def test_metadata_only_so_arm_adapter_probe_returns_metadata_result(tmp_path):
    device = tmp_path / "ttyUSB0"
    device.write_text("", encoding="utf-8")
    adapter = MetadataOnlySOArmAdapter(device_path=str(device))

    result = adapter.probe()

    assert isinstance(result, ArmProbeResult)
    assert result.ok is True
    assert result.identity.mode == AdapterMode.PROBE
    assert result.health.status == AdapterStatus.OK
    assert result.capabilities.can_move is False
    assert result.capabilities.can_enable_torque is False
    assert result.state is not None
    assert result.state.torque_enabled is False
    assert result.state.joints == ()
    assert result.state.metadata["path_exists"] is True
    assert result.state.metadata["device_path"] == str(device)
    assert result.state.metadata["serial_opened"] is False
    assert result.state.metadata["serial_commands_sent"] is False
    assert result.runtime == "metadata_only"


def test_metadata_only_so_arm_adapter_blocks_missing_device_without_touching_hardware(tmp_path):
    missing_device = tmp_path / "missing-ttyUSB0"
    adapter = MetadataOnlySOArmAdapter(device_path=str(missing_device))

    result = adapter.probe()

    assert result.ok is False
    assert result.health.status == AdapterStatus.UNAVAILABLE
    assert result.failure is not None
    assert result.failure.code == "hardware.device_path_missing"
    assert result.capabilities.can_move is False
    assert result.state is not None
    assert result.state.metadata["path_exists"] is False
    assert result.state.metadata["serial_opened"] is False


def test_metadata_only_so_arm_adapter_source_has_no_serial_or_actuator_operations():
    source = Path("robot/adapters/so_arm_metadata.py").read_text(encoding="utf-8")

    forbidden_snippets = [
        "serial.Serial",
        "import serial",
        "from serial",
        "os.open(",
        "open(",
        ".write(",
        ".read(",
        "enable_torque(",
        "torque_enabled = True",
        "move(",
        "actuate(",
        "import lerobot",
        "from lerobot",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source
