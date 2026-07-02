from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from robot.models import ValidationError


EVIDENCE_ROOT = PurePosixPath("data/evidence")


@dataclass
class EvidenceRef:
    evidence_id: str
    relative_path: str
    media_type: str
    capture_mode: str
    source_adapter: str
    linked_event_id: str
    checksum: str | None = None

    def __post_init__(self) -> None:
        required_strings = {
            "evidence_id": self.evidence_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "capture_mode": self.capture_mode,
            "source_adapter": self.source_adapter,
            "linked_event_id": self.linked_event_id,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValidationError(f"{field_name} is required")

        path = PurePosixPath(self.relative_path)
        if path.is_absolute():
            raise ValidationError("relative_path must be relative")
        if ".." in path.parts:
            raise ValidationError("relative_path must not contain parent traversal")

    def validate_for_task(self, task_id: str) -> None:
        expected_prefix = EVIDENCE_ROOT / task_id
        path = PurePosixPath(self.relative_path)
        if not path.is_relative_to(expected_prefix):
            raise ValidationError(f"relative_path must stay under {expected_prefix}")

    def local_path(self, base_path: Path | str = ".") -> Path:
        return Path(base_path) / self.relative_path

    def exists(self, base_path: Path | str = ".") -> bool:
        return self.local_path(base_path).is_file()

    def require_exists(self, base_path: Path | str = ".") -> None:
        if not self.exists(base_path):
            raise FileNotFoundError(f"evidence file is missing: {self.relative_path}")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "capture_mode": self.capture_mode,
            "source_adapter": self.source_adapter,
            "linked_event_id": self.linked_event_id,
        }
        if self.checksum is not None:
            data["checksum"] = self.checksum
        return data


def create_evidence_ref(
    *,
    task_id: str,
    evidence_id: str,
    variant: str,
    media_type: str,
    capture_mode: str,
    source_adapter: str,
    linked_event_id: str,
    checksum: str | None = None,
) -> EvidenceRef:
    if not task_id:
        raise ValidationError("task_id is required")
    if not variant:
        raise ValidationError("variant is required")
    if "/" in variant or "\\" in variant or variant == "..":
        raise ValidationError("variant must be a simple filename segment")

    evidence = EvidenceRef(
        evidence_id=evidence_id,
        relative_path=str(EVIDENCE_ROOT / task_id / f"{evidence_id}-{variant}.png"),
        media_type=media_type,
        capture_mode=capture_mode,
        source_adapter=source_adapter,
        linked_event_id=linked_event_id,
        checksum=checksum,
    )
    evidence.validate_for_task(task_id)
    return evidence
