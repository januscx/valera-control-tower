# Quest 3 rosbridge head client v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal Unity/OpenXR Quest 3 head client that sends the existing VR Gateway orientation contract through rosbridge and displays simulated neck events without touching hardware.

**Architecture:** Add a self-contained Unity project under `unity/ValeraQuestHeadClient/` that references the existing `unity/Valera.VrGateway` package through a local package dependency. Keep protocol/session/cadence/cleanup logic in pure C# classes testable without Unity, and keep Unity lifecycle, OpenXR pose acquisition, WebSocket callbacks, and debug UI in thin MonoBehaviour adapters. Use a narrow transport interface so a verified `ClientWebSocket` implementation can be swapped if Unity IL2CPP tooling is unavailable.

**Tech Stack:** Unity project assets, C#, UnityEngine, Unity XR/OpenXR APIs, .NET `ClientWebSocket` where supported, existing Valera DTO/codec/session/converter code, NUnit EditMode/PlayMode tests, ROS 2 Jazzy rosbridge.

## Global Constraints

- Base: PR #31 head `58476c2491af39da0e0a3d15d96a49b2f1c1b3d7`.
- Branch: `codex/quest3-rosbridge-head-client-v0-1`.
- Stacked draft PR against `codex/vr-gateway-ros2-runtime-smoke-v0-1`; never merge.
- Preserve existing gateway contract, safety policy, watchdog, neck controller, and hardware boundary.
- `timestamp_ms` uses monotonic `Stopwatch`, non-decreasing per session.
- No `head.pose` before confirmed `HEAD_ACTIVE`; pose cadence exactly 20 Hz with no catch-up queue.
- Cleanup sends best-effort `session.stop` only for an open socket and started session, then always stops loop/cancels receive/disposes transport.
- Only `Assets/`, `Packages/`, and `ProjectSettings/` Unity directories are committed; no generated output/APK.
- Pi5 rosbridge default remains loopback; LAN requires explicit address argument; allowlist remains the two VR Gateway topics.

---

### Task 1: Add failing pure C# protocol/session tests

**Files:**
- Create: `unity/ValeraQuestHeadClient/Assets/Tests/QuestHeadSessionTests.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Tests/RosbridgeEnvelopeCodecTests.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Tests/QuestHeadRuntimeSafetyTests.cs`

**Interfaces:**
- `QuestHeadSession` will expose `State`, `CanRecenter`, `CanSendPose`, `StartSession`, `BuildRecenter`, `BuildPose`, `BuildBestEffortStop`, `HandleEvent`, `ShouldSendPose`, and `Close`.
- `RosbridgeEnvelopeCodec.EncodePublish(topic, innerJson)`, `EncodeAdvertise(topic, type)`, and `EncodeSubscribe(topic)` return exact outer JSON; `DecodeMessageData(json)` returns the inner `msg.data`.
- A transport abstraction will expose open state, send, receive cancellation, and dispose behavior.

- [ ] Write failing tests for exact rosbridge envelopes and nested `msg.data`.
- [ ] Write failing tests for session start, `AWAITING_RECENTER`, recenter gating, `HEAD_ACTIVE`, pose gating, sequence/timestamp monotonicity, and no position.
- [ ] Write failing tests for 20 Hz no-catch-up behavior, state-invalidating events, malformed events/rejections, best-effort stop, pause/disconnect cleanup, and main-thread dispatch boundary.
- [ ] Run the tests with available C# test tooling; expected failure until implementation exists.

### Task 2: Implement pure C# transport/session core

**Files:**
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/Transport/RosbridgeEnvelopeCodec.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/Session/QuestHeadSession.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/Transport/IQuestTransport.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/Transport/ClientWebSocketQuestTransport.cs`

**Interfaces:**
- Envelope codec emits rosbridge `advertise`, `subscribe`, and `publish` messages with inner VR JSON in `msg.data`.
- Session uses `Stopwatch.GetTimestamp()` through an injectable monotonic clock and clamps timestamps non-decreasing.
- Session schedules one pose at a time at 20 Hz using next-deadline advancement, never a backlog.
- `ClientWebSocketQuestTransport` owns cancellation and disposal; callbacks are delivered to a caller-provided dispatcher.

- [ ] Implement the smallest code that makes Task 1 tests pass, reusing existing `WireCodec`, DTOs, `SessionSequence`, and `QuestLocalPoseConverter`.
- [ ] Keep socket errors and invalid gateway states terminal for pose sending.
- [ ] Run focused tests and refactor only while green.

### Task 3: Implement Unity project and client UI

**Files:**
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/QuestHeadClientBehaviour.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/QuestHeadPoseSource.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Runtime/QuestHeadDebugPanel.cs`
- Create: `unity/ValeraQuestHeadClient/Assets/Scenes/QuestHeadClient.unity`
- Create: `unity/ValeraQuestHeadClient/Assets/Prefabs/QuestHeadClient.prefab`
- Create: `unity/ValeraQuestHeadClient/Packages/manifest.json`
- Create: `unity/ValeraQuestHeadClient/Packages/packages-lock.json`
- Create: `unity/ValeraQuestHeadClient/ProjectSettings/ProjectVersion.txt`
- Create: `unity/ValeraQuestHeadClient/ProjectSettings/ProjectSettings.asset`
- Create: required `.meta` files under committed Unity directories.

- [ ] Add the minimal Android/OpenXR project settings, ARM64/IL2CPP target, and local package dependency for `Valera.VrGateway`.
- [ ] Wire Inspector-configured Pi5 address/port, Connect/Disconnect/Recenter controls, editor fallback orientation, and world-space status panel.
- [ ] Dispatch all Unity object access to main thread; stop pose loop on pause/focus loss/destroy.
- [ ] Add Unity EditMode/PlayMode tests and avoid generated directories.

### Task 4: Pi5 LAN launch and static safety checks

**Files:**
- Modify: `ros2/valera_vr_gateway/launch/valera_vr_gateway_with_rosbridge.launch.py`
- Modify: `tests/test_vr_gateway_ros_package.py`
- Modify: `docs/vr_gateway_ros2_runtime_smoke_v0_1.md`

- [ ] Verify default address remains `127.0.0.1`.
- [ ] Verify explicit `address:=<PI5_LAN_IP>` and `port:=9091` path without changing topic/services/params allowlists.
- [ ] Add static tests for forbidden topics/imports and no production hardware paths.
- [ ] Run isolated Pi5 launch smoke; do not alter live services or production workspace.

### Task 5: Full validation and stacked draft PR

**Files:**
- Create: `docs/quest3_rosbridge_head_client_v0_1.md`
- Modify: `README.md` only for a concise link if appropriate.

- [ ] Run full repository pytest, Unity tests if tooling exists, Android APK build if tooling exists, and `git diff --check`.
- [ ] If Unity/Android/ADB tools are unavailable, record exact `PENDING: tooling unavailable` results.
- [ ] If Quest is available, install APK and record observed gateway states, neck target example, watchdog result, and hardware topic proof; otherwise do not claim runtime PASS.
- [ ] Verify no generated Unity directories/APKs are tracked.
- [ ] Commit focused changes, push branch, and open a draft stacked PR titled `feat: add minimal Quest 3 rosbridge head client` against PR #31 branch.
- [ ] Report branch/head SHAs, changed files, build/test/runtime results, and Critical/Important/Minor findings.

## Self-review

- Protocol sequencing, monotonic time, 20 Hz no-catch-up, cleanup, Unity UI, Pi5 LAN safety, tests, documentation, and honest tooling reporting are covered.
- Existing gateway code and safety policy are outside the change set.
- The plan makes no Unity/Quest runtime claim without observed tooling/log evidence.
