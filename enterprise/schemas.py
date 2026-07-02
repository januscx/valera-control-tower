from robot.events import SCHEMA_VERSION


EVENT_ENVELOPE_REQUIRED_FIELDS = (
    "event_id",
    "task_id",
    "correlation_id",
    "sequence",
    "event_type",
    "occurred_at",
    "source",
    "mode",
    "schema_version",
    "payload",
    "evidence_refs",
)

EVENT_SCHEMA_VERSION = SCHEMA_VERSION
