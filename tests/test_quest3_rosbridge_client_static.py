"""Static repository checks for the Quest 3 Unity client slice."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "unity" / "ValeraQuestHeadClient"
RUNTIME = PROJECT / "Assets" / "Runtime"
LAUNCH = ROOT / "ros2" / "valera_vr_gateway" / "launch" / "valera_vr_gateway_with_rosbridge.launch.py"


def test_unity_project_has_only_source_facing_directories_and_required_settings():
    assert (PROJECT / "Assets").is_dir()
    assert (PROJECT / "Packages").is_dir()
    assert (PROJECT / "ProjectSettings").is_dir()
    assert (PROJECT / "ProjectSettings" / "ProjectVersion.txt").is_file()
    assert (PROJECT / "Packages" / "manifest.json").is_file()
    assert set(path.name for path in PROJECT.iterdir()) <= {
        "Assets",
        "Packages",
        "ProjectSettings",
    }


def test_unity_manifest_uses_existing_local_contract_package_without_forbidden_sdks():
    manifest = json.loads((PROJECT / "Packages" / "manifest.json").read_text())
    dependencies = manifest["dependencies"]
    assert dependencies["com.januscx.valera-vr-gateway"] == "file:../../Valera.VrGateway"
    assert any(name == "com.unity.xr.openxr" for name in dependencies)
    assert not any(
        forbidden in name.lower()
        for name in dependencies
        for forbidden in ("meta.xr", "interaction.toolkit", "ros#")
    )


def test_client_has_rosbridge_envelope_and_contract_pipeline():
    envelope = (RUNTIME / "Transport" / "RosbridgeEnvelopeCodec.cs").read_text()
    session = (RUNTIME / "Session" / "QuestHeadSession.cs").read_text()
    assert "msg" in envelope and "data" in envelope
    assert "WireCodec.EncodeCommand" in session
    assert "WireCodec.DecodeEvent" in session
    assert "SessionSequence" in session
    assert "QuestLocalPoseConverter" in session or "QuestLocalPoseConverter" in (
        RUNTIME / "QuestHeadPoseSource.cs"
    ).read_text()


def test_session_guards_pose_and_recenter_and_uses_monotonic_time():
    source = (RUNTIME / "Session" / "QuestHeadSession.cs").read_text()
    assert "AWAITING_RECENTER" in source
    # HEAD_ACTIVE renamed to ACTIVE in v0.2; C# updated in Tasks 6-7
    assert "ACTIVE" in source or "HEAD_ACTIVE" in source
    assert "CanSendPose" in source
    assert "CanRecenter" in source
    assert "Stopwatch" in source or "monotonic" in source.lower()
    assert "timestamp_ms" in source
    assert "HeadPose" in source
    assert "HeadRecenter" in source


def test_pose_scheduler_is_20hz_without_catch_up_and_cleanup_is_best_effort():
    session = (RUNTIME / "Session" / "QuestHeadSession.cs").read_text()
    behaviour = (RUNTIME / "QuestHeadClientBehaviour.cs").read_text()
    assert "20" in session or "0.05" in session
    assert "next" in session.lower() or "deadline" in session.lower()
    assert "session.stop" in session
    assert "best" in session.lower()
    assert "OnApplicationPause" in behaviour
    assert "OnApplicationFocus" in behaviour
    assert "OnDestroy" in behaviour
    # CancellationToken lives in VrGatewayWebSocket (extracted in v0.2)
    assert "CancellationToken" in behaviour or "gatewayWebSocket" in behaviour


def test_debug_panel_and_editor_fallback_exist():
    panel = (RUNTIME / "QuestHeadDebugPanel.cs").read_text()
    pose = (RUNTIME / "QuestHeadPoseSource.cs").read_text()
    assert "Connect" in panel
    assert "Disconnect" in panel
    assert "Recenter" in panel
    for field in ("session", "TX", "RX", "pan", "tilt", "error"):
        assert field.lower() in panel.lower()
    assert "UNITY_EDITOR" in pose


def test_client_source_has_no_hardware_or_forbidden_ros_topics():
    for path in PROJECT.rglob("*.cs"):
        source = path.read_text()
        assert "/cmd_vel" not in source
        assert "robot.adapters" not in source
        assert "SerialPort" not in source
        assert "GPIO" not in source
        assert "Dynamixel" not in source


def test_receive_events_are_dispatched_back_to_unity_main_thread():
    source = (RUNTIME / "QuestHeadClientBehaviour.cs").read_text()
    assert "ConcurrentQueue<Action>" in source
    assert "ManagedThreadId" in source
    assert "DrainMainThreadActions" in source
    assert "QueueMainThread" in source


def test_android_pose_path_uses_real_xr_head_device_and_never_editor_fallback():
    source = (RUNTIME / "QuestHeadPoseSource.cs").read_text()
    scene = (PROJECT / "Assets" / "Scenes" / "QuestHeadClient.unity").read_text()
    assert "InputDevices.GetDeviceAtXRNode" in source
    assert "XRNode.Head" in source
    assert "CommonUsages.deviceRotation" in source
    assert "#if !UNITY_EDITOR" in source
    assert "MainCamera" in scene


def test_lifecycle_has_reconnect_close_and_single_cleanup_guards():
    source = (RUNTIME / "QuestHeadClientBehaviour.cs").read_text()
    # VrGatewayWebSocket wraps ClientWebSocketQuestTransport (v0.2 refactor)
    assert "new VrGatewayWebSocket()" in source or "new ClientWebSocketQuestTransport()" in source
    assert "cleanupGate.TryClaim()" in source
    assert "cleanupGate.Release()" in source
    assert "connecting" in source
    assert "stopping = false" in source
    # These patterns may live in VrGatewayWebSocket (v0.2 refactor)
    transport = (RUNTIME / "Transport" / "VrGatewayWebSocket.cs").read_text() if (RUNTIME / "Transport" / "VrGatewayWebSocket.cs").exists() else ""
    assert "Remote WebSocket close frame received" in source or "Remote WebSocket close frame received" in transport
    assert "if (envelope == null)" in source or "if (envelope == null)" in transport
    assert "SendCommandSafely" in source or "SendCommandSafely" in transport
    assert "catch (Exception exception)" in source
    assert "transport?.Dispose()" in source or "transport?.Dispose()" in transport
    assert "session.Close()" in source


def test_behaviour_connect_guard_reopens_only_after_cleanup_resets_stopping():
    source = (RUNTIME / "QuestHeadClientBehaviour.cs").read_text()
    connect_guard = source.split("public void Connect()", 1)[1].split("_ = ConnectRoutine", 1)[0]
    cleanup_tail = source.split("private async Task CleanupRoutine", 1)[1]
    assert "stopping" in connect_guard
    assert "if (!destroyed)" in cleanup_tail
    assert cleanup_tail.index("stopping = false") < cleanup_tail.index("cleanupGate.Release()")


def test_pi5_rosbridge_launch_keeps_explicit_lan_opt_in_and_exact_allowlist():
    source = LAUNCH.read_text()
    assert 'DeclareLaunchArgument("rosbridge_address", default_value="127.0.0.1")' in source
    assert 'DeclareLaunchArgument("rosbridge_port", default_value="9090")' in source
    assert "/valera/vr_gateway/command" in source
    assert "/valera/vr_gateway/event" in source
    assert "services_glob" in source and "params_glob" in source
    assert "/cmd_vel" not in source
