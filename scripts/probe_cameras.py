from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class CameraProfile:
    name: str
    path: str
    width: int
    height: int
    fps: int
    fourcc: str


DEFAULT_PROFILES: dict[str, CameraProfile] = {
    "innomaker": CameraProfile(
        name="innomaker",
        path="/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0",
        width=1920,
        height=1080,
        fps=30,
        fourcc="MJPG",
    ),
    "astra_pro": CameraProfile(
        name="astra_pro",
        path="/dev/v4l/by-id/usb-Astra_Pro_HD_Camera_Astra_Pro_HD_Camera-video-index0",
        width=1280,
        height=720,
        fps=30,
        fourcc="MJPG",
    ),
}


def _require_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for camera probing. Install requirements-dev.txt."
        ) from exc
    return cv2


def select_profiles(camera_args: list[str] | None) -> list[CameraProfile]:
    """Return the profiles requested by the user, or all defaults if none given."""
    if not camera_args:
        return list(DEFAULT_PROFILES.values())

    names: list[str] = []
    for arg in camera_args:
        names.extend(name.strip() for name in arg.split(",") if name.strip())

    selected: list[CameraProfile] = []
    for name in names:
        profile = DEFAULT_PROFILES.get(name)
        if profile is None:
            valid = ", ".join(sorted(DEFAULT_PROFILES))
            raise ValueError(f"unknown camera '{name}'; valid choices: {valid}")
        selected.append(profile)

    # Preserve default order while keeping only the first occurrence of a name.
    seen: set[str] = set()
    deduped: list[CameraProfile] = []
    for profile in selected:
        if profile.name not in seen:
            seen.add(profile.name)
            deduped.append(profile)
    return deduped


def probe_camera(
    profile: CameraProfile,
    output_path: Path,
    cv2_module: Any | None = None,
) -> dict[str, Any]:
    """Open one camera, set its mode, capture a frame, and write a JPEG."""
    cv2 = cv2_module or _require_cv2()
    result: dict[str, Any] = {
        "name": profile.name,
        "configured_path": profile.path,
        "requested_width": profile.width,
        "requested_height": profile.height,
        "requested_fps": profile.fps,
        "requested_fourcc": profile.fourcc,
        "ok": False,
        "frame_path": None,
        "error": None,
    }

    device = Path(profile.path)
    if not device.exists():
        result["error"] = f"device path does not exist: {profile.path}"
        return result

    resolved = device.resolve()
    result["resolved_path"] = str(resolved)

    capture = None
    try:
        capture = cv2.VideoCapture(str(resolved), cv2.CAP_V4L2)
        if not capture.isOpened():
            result["error"] = f"could not open {profile.path} (resolved: {resolved})"
            return result

        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*profile.fourcc))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, profile.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, profile.height)
        capture.set(cv2.CAP_PROP_FPS, profile.fps)

        ok, frame = capture.read()
        if not ok or frame is None:
            result["error"] = f"could not read one frame from {profile.path}"
            return result

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), frame):
            result["error"] = f"failed to write frame to {output_path}"
            return result

        result["ok"] = True
        result["frame_path"] = str(output_path)
        result["actual_width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        result["actual_height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        result["actual_fps"] = int(capture.get(cv2.CAP_PROP_FPS))
    except Exception as exc:  # pragma: no cover - defensive catch for unexpected cv2 errors
        result["error"] = f"cv2 error for {profile.path}: {exc}"
        return result
    finally:
        if capture is not None:
            capture.release()

    return result


def write_report(results: list[dict[str, Any]], output_path: Path) -> None:
    """Write a Markdown summary of the probe results."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Dual-camera probe report",
        "",
        f"Generated: {timestamp}",
        "",
        "| Camera | OK | Configured path | Resolved path | Frame | Error |",
        "|--------|----|-----------------|---------------|-------|-------|",
    ]

    for result in results:
        lines.append(
            "| {name} | {ok} | {configured_path} | {resolved_path} | {frame_path} | {error} |".format(
                name=result["name"],
                ok="yes" if result["ok"] else "no",
                configured_path=result.get("configured_path", ""),
                resolved_path=result.get("resolved_path", ""),
                frame_path=result.get("frame_path") or "",
                error=result.get("error") or "",
            )
        )

    lines.append("")
    lines.append("## Details")
    lines.append("")

    for result in results:
        lines.append(f"### {result['name']}")
        lines.append("")
        lines.append(f"- Configured path: `{result.get('configured_path', '')}`")
        lines.append(f"- Resolved path: `{result.get('resolved_path', '')}`")
        lines.append(
            f"- Requested mode: {result.get('requested_width')}x{result.get('requested_height')} "
            f"@{result.get('requested_fps')}fps {result.get('requested_fourcc')}"
        )
        if "actual_width" in result:
            lines.append(
                f"- Actual mode: {result.get('actual_width')}x{result.get('actual_height')} "
                f"@{result.get('actual_fps')}fps"
            )
        lines.append(f"- Frame written: `{result.get('frame_path') or 'none'}`")
        if result.get("error"):
            lines.append(f"- Error: `{result['error']}`")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe Valera's dual cameras by stable v4l by-id paths."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tmp/camera-probe",
        help="directory for JPEG frames and report (default: tmp/camera-probe)",
    )
    parser.add_argument(
        "--camera",
        action="append",
        dest="cameras",
        help="camera name to probe; repeatable or comma-separated (default: all)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    try:
        profiles = select_profiles(args.cameras)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for profile in profiles:
        output_path = output_dir / f"{profile.name}.jpg"
        result = probe_camera(profile, output_path)
        results.append(result)

    report_path = output_dir / "report.md"
    write_report(results, report_path)

    print("Dual-camera probe complete.")
    print(f"Report: {report_path}")
    for result in results:
        status = "OK" if result["ok"] else "FAIL"
        frame_info = ""
        if result.get("frame_path"):
            frame_info = f" -> {result['frame_path']}"
        error_info = f" ({result['error']})" if result.get("error") else ""
        print(f"  [{status}] {result['name']}{frame_info}{error_info}")

    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
