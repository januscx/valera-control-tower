from dataclasses import dataclass
from html import escape
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True)
class DashboardSummary:
    task_id: str
    correlation_id: str
    final_status: str
    event_count: int


def render_dashboard(events: list[dict], output_path: Path) -> DashboardSummary:
    summary = summarize_events(events)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_html(events, summary, output_path), encoding="utf-8")
    return summary


def render_dashboard_from_replay(replay_path: Path, output_path: Path) -> DashboardSummary:
    events = json.loads(replay_path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("replay JSON must contain a list of events")
    return render_dashboard(events, output_path)


def summarize_events(events: list[dict]) -> DashboardSummary:
    first_event = events[0] if events else {}
    last_event = events[-1] if events else {}
    return DashboardSummary(
        task_id=str(first_event.get("task_id", "unknown")),
        correlation_id=str(first_event.get("correlation_id", "unknown")),
        final_status=_final_status(last_event),
        event_count=len(events),
    )


def _final_status(last_event: dict) -> str:
    event_type = last_event.get("event_type")
    payload = last_event.get("payload", {})
    payload_status = payload.get("status") if isinstance(payload, dict) else None

    if event_type == "task.completed" or payload_status == "completed":
        return "completed"
    if event_type == "task.failed" or "error" in last_event:
        return "failed"
    return "in progress / unknown"


def _render_html(events: list[dict], summary: DashboardSummary, output_path: Path) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Valera Mission Dashboard - {_html(summary.task_id)}</title>
  <style>
    body {{
      color: #172026;
      font-family: Arial, sans-serif;
      line-height: 1.45;
      margin: 2rem;
    }}
    header, section {{
      margin-bottom: 2rem;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border: 1px solid #c8d0d6;
      padding: 0.5rem;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #edf2f4;
    }}
    pre {{
      background: #f6f8fa;
      border: 1px solid #d8dee4;
      overflow-x: auto;
      padding: 0.75rem;
      white-space: pre-wrap;
    }}
    article {{
      border-top: 1px solid #d8dee4;
      padding: 1rem 0;
    }}
    article:first-of-type {{
      border-top: 0;
    }}
    .evidence-list {{
      display: grid;
      gap: 0.75rem;
      list-style: none;
      padding-left: 0;
    }}
    .evidence-list li {{
      border: 1px solid #d8dee4;
      padding: 0.75rem;
    }}
    .evidence-link {{
      margin-top: 0.5rem;
    }}
    .evidence-preview {{
      border: 1px solid #c8d0d6;
      display: block;
      height: auto;
      margin-top: 0.5rem;
      max-width: min(420px, 100%);
    }}
    .summary {{
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }}
    .summary div {{
      border: 1px solid #c8d0d6;
      padding: 0.75rem;
    }}
    .label {{
      color: #52616b;
      display: block;
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Valera Mission Dashboard</h1>
    <h2>Task {_html(summary.task_id)}</h2>
    <div class="summary">
      <div><span class="label">Final status</span>{_html(summary.final_status)}</div>
      <div><span class="label">Correlation id</span>{_html(summary.correlation_id)}</div>
      <div><span class="label">Event count</span>{summary.event_count}</div>
    </div>
  </header>
  <section>
    <h2>Event Timeline</h2>
    <table>
      <thead>
        <tr>
          <th>Sequence</th>
          <th>Occurred at</th>
          <th>Event type</th>
          <th>Source</th>
          <th>Mode</th>
          <th>Payload status</th>
        </tr>
      </thead>
      <tbody>
{_timeline_rows(events)}
      </tbody>
    </table>
  </section>
  <section>
    <h2>Event Details</h2>
{_detail_sections(events, output_path)}
  </section>
</body>
</html>
"""


def _timeline_rows(events: list[dict]) -> str:
    return "\n".join(
        "        <tr>"
        f"<td>{_html(event.get('sequence', ''))}</td>"
        f"<td>{_html(event.get('occurred_at', ''))}</td>"
        f"<td>{_html(event.get('event_type', ''))}</td>"
        f"<td>{_html(event.get('source', ''))}</td>"
        f"<td>{_html(event.get('mode', ''))}</td>"
        f"<td>{_html(_payload_status(event))}</td>"
        "</tr>"
        for event in events
    )


def _detail_sections(events: list[dict], output_path: Path) -> str:
    return "\n".join(_detail_section(event, output_path) for event in events)


def _detail_section(event: dict, output_path: Path) -> str:
    sequence = _html(event.get("sequence", ""))
    event_type = _html(event.get("event_type", ""))
    return f"""    <article>
      <h3>{sequence}. {event_type}</h3>
      <h4>Payload summary</h4>
      <pre>{_html(_json_summary(event.get("payload", {})))}</pre>
{_evidence_section(event.get("evidence_refs", []), output_path)}
{_error_section(event.get("error"))}
    </article>"""


def _evidence_section(evidence_refs: Any, output_path: Path) -> str:
    if not evidence_refs:
        return "      <p>No evidence refs.</p>"
    if not isinstance(evidence_refs, list):
        evidence_refs = [evidence_refs]

    items = "\n".join(
        f"        <li>{_evidence_ref_summary(ref, output_path)}</li>" for ref in evidence_refs
    )
    return f"""      <h4>Evidence refs</h4>
      <ul class="evidence-list">
{items}
      </ul>"""


def _evidence_ref_summary(ref: Any, output_path: Path) -> str:
    if isinstance(ref, dict):
        fields = [
            ("evidence_id", ref.get("evidence_id")),
            ("relative_path", ref.get("relative_path")),
            ("media_type", ref.get("media_type")),
            ("capture_mode", ref.get("capture_mode")),
            ("source_adapter", ref.get("source_adapter")),
            ("checksum", ref.get("checksum")),
        ]
        present_fields = [f"{label}: {_html(value)}" for label, value in fields if value is not None]
        return "; ".join(present_fields) + _evidence_link_and_preview(ref, output_path)
    return f"legacy_ref: {_html(ref)}"


def _evidence_link_and_preview(ref: dict, output_path: Path) -> str:
    relative_path = ref.get("relative_path")
    if not isinstance(relative_path, str) or not _is_safe_evidence_path(relative_path):
        return ""

    href = _relative_href_from_dashboard(relative_path, output_path)
    html = f'\n          <div class="evidence-link"><a href="{_html(href)}">Open evidence file</a></div>'
    if ref.get("media_type") == "image/png":
        evidence_id = ref.get("evidence_id", "evidence")
        html += (
            f'\n          <img src="{_html(href)}" '
            f'alt="Evidence preview for {_html(evidence_id)}" class="evidence-preview">'
        )
    return html


def _is_safe_evidence_path(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.is_relative_to(PurePosixPath("data/evidence"))
    )


def _relative_href_from_dashboard(relative_path: str, output_path: Path) -> str:
    output_parent = output_path.parent
    root_path = _dashboard_root(output_path)
    evidence_path = root_path.joinpath(*PurePosixPath(relative_path).parts)
    return os.path.relpath(evidence_path, start=output_parent).replace(os.sep, "/")


def _dashboard_root(output_path: Path) -> Path:
    parts = output_path.parts[:-1]
    if "data" not in parts:
        return output_path.parent

    data_index = len(parts) - 1 - list(reversed(parts)).index("data")
    if data_index == 0:
        return Path(".")
    return Path(*parts[:data_index])


def _error_section(error: Any) -> str:
    if not isinstance(error, dict):
        return ""
    return f"""      <h4>Error details</h4>
      <p>error.code: {_html(error.get("code", ""))}</p>
      <p>error.message: {_html(error.get("message", ""))}</p>"""


def _payload_status(event: dict) -> str:
    payload = event.get("payload", {})
    if isinstance(payload, dict):
        return str(payload.get("status", ""))
    return ""


def _json_summary(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _html(value: Any) -> str:
    return escape(str(value), quote=True)
