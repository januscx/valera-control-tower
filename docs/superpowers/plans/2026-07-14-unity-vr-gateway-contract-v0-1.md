# Unity VR Gateway Contract v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an importable Unity package that strictly encodes, decodes, and converts the VR Gateway v0.1 client contract without runtime integrations.

**Architecture:** Behavior-free serializable DTOs live in `Runtime/Contracts`. A handwritten structural parser validates JSON before `JsonUtility`; the codec reads a minimal header, selects one DTO, then runs semantic validation. A pure quaternion converter owns the Unity-to-canonical basis conversion.

**Tech Stack:** Unity package layout, C#, `UnityEngine`, `JsonUtility`, Unity Test Framework NUnit.

## Global Constraints

- Package path: `unity/Valera.VrGateway/`; no Unity project is committed.
- No runtime package dependencies, ROS, networking, XR runtime, hardware, or external JSON parser.
- DTOs are `[Serializable]` public snake_case fields; wire enums are exact strings.
- JSON limit: 65,536 UTF-8 bytes or UTF-16 units; depth: 16.
- Wire integers are literal `0..Int64.MaxValue`; command sequence starts at one and never wraps.
- Quaternion conversion is `(-x, -y, z, w)` after normalization; fixtures compare rotations, not signs.

---

### Task 1: Package manifest and DTO contract

**Files:**
- Create: `unity/Valera.VrGateway/package.json`
- Create: `unity/Valera.VrGateway/Runtime/Valera.VrGateway.Runtime.asmdef`
- Create: `unity/Valera.VrGateway/Runtime/Contracts/WireDtos.cs`
- Create: `unity/Valera.VrGateway/Tests/Runtime/Valera.VrGateway.Runtime.Tests.asmdef`
- Test: `unity/Valera.VrGateway/Tests/Runtime/WireDtoTests.cs`

**Interfaces:** Produces `[Serializable]` public-field DTOs and exact wire string constants for every v0.1 command/event.

- [ ] **Step 1: Write failing reflection tests for snake_case DTO fields and exact schema strings.**
- [ ] **Step 2: Run `UNITY=/path/to/Unity ./scripts/test_unity_vr_gateway_package.sh`; confirm the missing DTO failure.**
- [ ] **Step 3: Add DTOs with no behavior, plus runtime/test assembly definitions and package manifest.**
- [ ] **Step 4: Re-run fixtures and commit `feat: add Unity VR gateway wire models`.**

### Task 2: Strict structural parser and two-pass codec

**Files:**
- Create: `unity/Valera.VrGateway/Runtime/Json/StrictJsonParser.cs`
- Create: `unity/Valera.VrGateway/Runtime/Json/WireCodec.cs`
- Test: `unity/Valera.VrGateway/Tests/Runtime/StrictJsonParserTests.cs`
- Test: `unity/Valera.VrGateway/Tests/Runtime/WireCodecTests.cs`

**Interfaces:** `WireCodec.DecodeCommand(string)` and `DecodeEvent(string)` return one validated exact DTO or throw `WireValidationException`; `Encode...` validates before `JsonUtility.ToJson`.

- [ ] **Step 1: Write failing fixtures for duplicate decoded keys (`"x"`/`"\\u0078"`), invalid escapes/surrogates, comments, trailing JSON, depth/size, nonstandard numbers, overflow, missing/extra fields, and wrong types.**
- [ ] **Step 2: Run the host fixture and confirm parser/codec failure.**
- [ ] **Step 3: Implement a standard-JSON recursive parser with string-decoded duplicate detection; validate header, choose DTO by string discriminator, deserialize with `JsonUtility`, and validate semantics/allowed fields.**
- [ ] **Step 4: Add JSON round trips and negatives for every command/event; re-run fixtures and commit `feat: validate Unity VR gateway JSON contract`.**

### Task 3: Quaternion conversion and session helpers

**Files:**
- Create: `unity/Valera.VrGateway/Runtime/OpenXr/QuestLocalPoseConverter.cs`
- Create: `unity/Valera.VrGateway/Runtime/Session/SessionSequence.cs`
- Test: `unity/Valera.VrGateway/Tests/Runtime/QuestLocalPoseConverterTests.cs`
- Test: `unity/Valera.VrGateway/Tests/Runtime/SessionSequenceTests.cs`

**Interfaces:** `QuestLocalPoseConverter.Convert(Quaternion)` returns normalised canonical rotation; `SessionSequence.Next()` returns `long` or explicitly fails at maximum.

- [ ] **Step 1: Write failing basis-vector fixtures for identity, ±yaw, ±pitch, roll, normalization, q/-q equivalence, recenter-relative orientation, Unity forward conversion, and sequence overflow.**
- [ ] **Step 2: Run the host fixture and confirm converter/helper failure.**
- [ ] **Step 3: Implement validation and `new Quaternion(-q.x, -q.y, q.z, q.w)` without Euler angles or sign canonicalization; implement bounded sequence helper.**
- [ ] **Step 4: Re-run fixtures and commit `feat: convert Unity poses for VR gateway`.**

### Task 4: README and ephemeral host validation

**Files:**
- Create: `unity/Valera.VrGateway/README.md`
- Create: `scripts/test_unity_vr_gateway_package.sh`
- Test: `unity/Valera.VrGateway/Tests/Runtime/WireCodecRoundTripTests.cs`

**Interfaces:** The shell script creates a temporary outside-repository host project that imports the local package and invokes edit-mode NUnit tests using an explicitly supplied Unity executable.

- [ ] **Step 1: Write failing all-command/all-event round-trip fixtures.**
- [ ] **Step 2: Run host and confirm the incomplete codec fixture fails.**
- [ ] **Step 3: Add deterministic literals copied from Python cases, the package README, and safe temporary-host script.**
- [ ] **Step 4: Run available host, Python, and diff checks; commit `docs: validate Unity VR gateway package`.**

### Task 5: Draft PR

**Files:** No source changes.

- [ ] **Step 1: Inspect `git diff --name-only origin/main...HEAD`; permit only Unity package, test script, and Unity contract docs.**
- [ ] **Step 2: Push `codex/unity-vr-gateway-contract-v0-1` and create a draft PR targeting `main`.**
- [ ] **Step 3: If Unity is unavailable, state the host test is ready but unexecuted and leave the PR draft.**
