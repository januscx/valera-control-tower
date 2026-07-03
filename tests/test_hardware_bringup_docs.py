from pathlib import Path


def test_wiring_readiness_checklist_covers_operator_safety_boundaries():
    doc = Path("docs/hardware_bringup_v0.md").read_text(encoding="utf-8")

    required_phrases = [
        "SO-ARM wiring and arm readiness handoff",
        "physically label the CH340 USB adapter",
        "confirm arm power state",
        "confirm controller board is connected to the correct servo bus",
        "confirm servo cable orientation",
        "confirm no loose wires",
        "confirm the arm is mechanically supported",
        "confirm gripper and links are clear of obstacles",
        "confirm emergency power cut is available",
        "confirm tracks/base are disabled or off-ground",
        "confirm no human fingers are inside pinch or motion zones",
        "confirm torque and motion phases have not started yet",
        "--plan-identity-state-query",
        "--enable-non-actuating-identity-query",
        "--confirm-send-non-actuating-identity-query-bytes",
        "ff ff 01 02 01 fb",
        "not passive serial inspection",
        "--enable-serial-open-close-check",
    ]
    for phrase in required_phrases:
        assert phrase in doc
