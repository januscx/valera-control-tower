# Valera VR Gateway Unity Contract v0.1

`com.januscx.valera-vr-gateway` is a reusable, transport-neutral Unity package
for the client side of the Valera VR Gateway v0.1 contract. It is not a Unity
project and contains no scene, XR runtime integration, controller bindings,
networking, ROS, rosbridge, WebRTC, video, or hardware code.

## Installation

Add this local package through Unity Package Manager, or add a `file:` entry
for `unity/Valera.VrGateway` to a consuming project's `Packages/manifest.json`.
The package requires Unity 6000.0 or later and uses only `UnityEngine` and
`JsonUtility` at runtime.

## Contract boundary

The package mirrors schema version `"0.1"`, the six input command names, and
the four output event names from `robot/vr_gateway/messages.py`. Wire DTOs use
`[Serializable]` public fields with exact snake_case names. Wire enumerations
remain strings and are mapped/validated explicitly; C# enum serialization is
not used.

`WireCodec` runs a strict parser before `JsonUtility`: JSON is capped at 65,536
bytes/UTF-16 code units and depth 16; it rejects duplicate decoded keys,
malformed Unicode, comments, trailing input, trailing commas, unsupported
schema/discriminators, wrong field sets, and unsafe values. Integer fields only
accept literal values in `0..Int64.MaxValue`; command sequence starts at one.

`QuestLocalPoseConverter.Convert` normalizes a valid Unity quaternion and maps
`(x, y, z, w)` to `(-x, -y, z, w)`, which implements
`R_openxr = S * R_unity * S` for `S = diag(1, 1, -1)`. Quaternion sign is not
canonicalized: `q` and `-q` remain equivalent rotations.

## Tests

Run the package's runtime NUnit fixtures through an ephemeral, untracked Unity
host project:

```bash
UNITY=/home/janus/Unity/Hub/Editor/6000.3.19f1/Editor/Unity \
  scripts/test_unity_vr_gateway_package.sh
```

The runner creates and removes its host below `/tmp`; it never creates a Unity
project inside this repository. ALSA/FMOD warnings from a headless Linux editor
are expected and do not indicate an audio dependency in this package.
