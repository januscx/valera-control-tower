#!/usr/bin/env bash
set -euo pipefail

: "${UNITY:?Set UNITY to a Unity Editor executable.}"
package_path=$(cd "$(dirname "$0")/.." && pwd)
host=$(mktemp -d /tmp/valera-vr-gateway-unity-host.XXXXXX)
results="$host/results.xml"
trap 'rm -rf "$host"' EXIT

"$UNITY" -batchmode -nographics -quit -createProject "$host" -logFile "$host/create.log"
python3 - "$host/Packages/manifest.json" "$package_path" <<'PY'
import json
import sys

manifest_path, package_path = sys.argv[1:]
with open(manifest_path, encoding="utf-8") as source:
    manifest = json.load(source)
manifest["dependencies"]["com.januscx.valera-vr-gateway"] = "file:" + package_path
manifest["dependencies"]["com.unity.test-framework"] = "1.5.1"
manifest["testables"] = ["com.januscx.valera-vr-gateway"]
with open(manifest_path, "w", encoding="utf-8") as destination:
    json.dump(manifest, destination, indent=2)
    destination.write("\n")
PY

"$UNITY" -batchmode -nographics -projectPath "$host" -runTests \
  -testPlatform EditMode -assemblyNames Valera.VrGateway.Runtime.Tests \
  -testResults "$results" -logFile "$host/test.log"
grep -q 'result="Passed"' "$results"
