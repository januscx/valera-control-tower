# Final Fix Report

**Status:** All 4 findings fixed, all 467 tests pass.

## Changes

| # | Finding | File | Change |
|---|---------|------|--------|
| 1 | Critical — encoder rejects ARM watchdog `command_zeroed=True` with empty `joint_velocity` | `robot/vr_gateway/wire.py:659` | Changed validation to allow empty dict when `command_zeroed=True` |
| 2 | Important — Unity `GatewayStateStore` never called in event handling | `unity/ValeraQuestHeadClient/Assets/Runtime/QuestHeadClientBehaviour.cs` | Added `[SerializeField] GatewayStateStore _stateStore`, calls `UpdateFromEvent` in `HandleInbound` via `EventEnvelopeDto` helper |
| 3 | Important — C# `ArmJogPayload.joint_velocity` has wrong type | `unity/ValeraQuestHeadClient/Assets/Runtime/Transport/GatewayMessages.cs` | Kept as `string`, added comment explaining `JsonUtility` Dictionary limitation |
| 4 | Important — `_handle_mode_set_head` returns `()` without `GatewayStateEvent` | `robot/vr_gateway/gateway.py:336` | Now returns `GatewayStateEvent(now_ns, self.state, self.current_mode, ...)` |

## Tests Added

- `test_encode_arm_target_event_with_command_zeroed_allows_empty_dict` — verifies `encode_event(ArmTargetEvent(..., command_zeroed=True, joint_velocity={}))` produces valid JSON
- `test_mode_set_drive_to_head_emits_gateway_state_event` — verifies `mode.set("head")` from DRIVE emits `GatewayStateEvent` with `HEAD_ONLY`
- Updated `test_equal_timestamp_with_higher_sequence_is_accepted_with_state_event` (was `_without_state_event`) — verifies mode.set("head") emits state event
- Updated `test_bridge_publishes_state_event_on_mode_set_head` (was `_publishes_nothing`) — verifies ROS bridge publishes state event

## Commits

```
fix: address final review findings — encoder ARM watchdog, Unity store wiring, C# joint_velocity type, mode_set_head event
```

## Concerns

None. All 467 tests pass (7 skipped).
