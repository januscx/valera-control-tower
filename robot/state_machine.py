from dataclasses import dataclass, field

from robot.events import EventEnvelope, EventType
from robot.models import ValidationError


TERMINAL_EVENT_TYPES = {EventType.TASK_COMPLETED, EventType.TASK_FAILED}


@dataclass
class TaskEventLog:
    task_id: str
    events: list[EventEnvelope] = field(default_factory=list)

    @property
    def terminal_event_type(self) -> EventType | None:
        for event in self.events:
            if event.event_type in TERMINAL_EVENT_TYPES:
                return event.event_type
        return None

    @property
    def last_sequence(self) -> int:
        if not self.events:
            return 0
        return self.events[-1].sequence

    def append(self, event: EventEnvelope) -> None:
        if event.task_id != self.task_id:
            raise ValidationError("event task_id does not match event log task_id")

        if self.terminal_event_type is not None:
            raise ValidationError("cannot append event after terminal state")

        if event.sequence <= self.last_sequence:
            raise ValidationError("event sequence must be monotonic per task")

        self.events.append(event)

    def validate(self) -> None:
        seen_terminal: EventType | None = None
        last_sequence = 0

        for event in self.events:
            if event.task_id != self.task_id:
                raise ValidationError("event task_id does not match event log task_id")
            if event.sequence <= last_sequence:
                raise ValidationError("event sequence must be monotonic per task")
            if seen_terminal is not None:
                raise ValidationError("cannot append event after terminal state")
            if event.event_type in TERMINAL_EVENT_TYPES:
                seen_terminal = event.event_type
            last_sequence = event.sequence
