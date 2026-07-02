from pathlib import Path

from dashboard.render import render_dashboard, render_dashboard_from_replay


def sample_events() -> list[dict]:
    return [
        {
            "event_id": "event-001",
            "task_id": "task-123",
            "correlation_id": "corr-123",
            "sequence": 1,
            "event_type": "task.created",
            "occurred_at": "2026-07-02T12:00:00+00:00",
            "source": "valera.test",
            "mode": "simulation",
            "payload": {"status": "created", "note": "<script>alert('x')</script>"},
            "evidence_refs": ["legacy-frame-001"],
        },
        {
            "event_id": "event-002",
            "task_id": "task-123",
            "correlation_id": "corr-123",
            "sequence": 2,
            "event_type": "object.found",
            "occurred_at": "2026-07-02T12:00:01+00:00",
            "source": "valera.vision",
            "mode": "real_vision",
            "payload": {"status": "found"},
            "evidence_refs": [
                {
                    "evidence_id": "evidence-001",
                    "relative_path": "data/evidence/task-123/evidence-001-detected.png",
                    "media_type": "image/png",
                    "capture_mode": "fixture",
                    "source_adapter": "real_vision.fixture",
                    "checksum": "sha256:abc123",
                }
            ],
        },
        {
            "event_id": "event-003",
            "task_id": "task-123",
            "correlation_id": "corr-123",
            "sequence": 3,
            "event_type": "object.not_found",
            "occurred_at": "2026-07-02T12:00:02+00:00",
            "source": "valera.vision",
            "mode": "real_vision",
            "payload": {"status": "not_found"},
            "evidence_refs": [],
            "error": {"code": "OBJECT_NOT_FOUND", "message": "Marker was not found"},
        },
    ]


def test_dashboard_renderer_creates_html_file_from_event_dicts(tmp_path: Path):
    output_path = tmp_path / "dashboard" / "index.html"

    summary = render_dashboard(sample_events(), output_path)

    assert output_path.is_file()
    assert summary.task_id == "task-123"


def test_dashboard_html_includes_mission_summary(tmp_path: Path):
    output_path = tmp_path / "index.html"

    summary = render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "task-123" in html
    assert "corr-123" in html
    assert "failed" in html
    assert "Event count" in html
    assert ">3<" in html
    assert summary.final_status == "failed"
    assert summary.event_count == 3


def test_dashboard_timeline_includes_sequence_event_type_and_payload_status(tmp_path: Path):
    output_path = tmp_path / "index.html"

    render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "<td>1</td>" in html
    assert "task.created" in html
    assert "object.found" in html
    assert "created" in html
    assert "not_found" in html


def test_dashboard_renders_structured_and_legacy_evidence_refs(tmp_path: Path):
    output_path = tmp_path / "index.html"

    render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "legacy-frame-001" in html
    assert "evidence-001" in html
    assert "data/evidence/task-123/evidence-001-detected.png" in html
    assert "image/png" in html
    assert "fixture" in html
    assert "real_vision.fixture" in html
    assert "sha256:abc123" in html


def test_dashboard_renders_safe_evidence_image_ref_as_link_and_preview(tmp_path: Path):
    output_path = tmp_path / "data" / "runs" / "task-123" / "dashboard.html"

    render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    expected_href = "../../evidence/task-123/evidence-001-detected.png"
    assert f'<a href="{expected_href}">' in html
    assert (
        f'<img src="{expected_href}" '
        'alt="Evidence preview for evidence-001" class="evidence-preview">'
    ) in html


def test_dashboard_does_not_link_or_preview_unsafe_absolute_evidence_path(tmp_path: Path):
    output_path = tmp_path / "index.html"
    events = sample_events()
    events[1]["evidence_refs"][0]["relative_path"] = "/data/evidence/task-123/absolute.png"

    render_dashboard(events, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "/data/evidence/task-123/absolute.png" in html
    assert 'href="/data/evidence/task-123/absolute.png"' not in html
    assert 'src="/data/evidence/task-123/absolute.png"' not in html


def test_dashboard_does_not_link_or_preview_parent_traversal_evidence_path(tmp_path: Path):
    output_path = tmp_path / "index.html"
    events = sample_events()
    events[1]["evidence_refs"][0]["relative_path"] = "data/evidence/../secret.png"

    render_dashboard(events, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "data/evidence/../secret.png" in html
    assert 'href="data/evidence/../secret.png"' not in html
    assert 'src="data/evidence/../secret.png"' not in html


def test_dashboard_does_not_preview_non_image_evidence_ref(tmp_path: Path):
    output_path = tmp_path / "index.html"
    events = sample_events()
    events[1]["evidence_refs"][0]["media_type"] = "application/json"

    render_dashboard(events, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert 'href="data/evidence/task-123/evidence-001-detected.png"' in html
    assert "<img" not in html


def test_dashboard_escapes_html_in_evidence_ref_fields(tmp_path: Path):
    output_path = tmp_path / "index.html"
    events = sample_events()
    events[1]["evidence_refs"][0]["evidence_id"] = "<script>alert('id')</script>"
    events[1]["evidence_refs"][0]["relative_path"] = (
        "data/evidence/task-123/<script>alert('path')</script>.png"
    )

    render_dashboard(events, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "<script>alert('id')</script>" not in html
    assert "<script>alert('path')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;id&#x27;)&lt;/script&gt;" in html
    assert "&lt;script&gt;alert(&#x27;path&#x27;)&lt;/script&gt;" in html


def test_dashboard_renders_error_details_for_not_found_event(tmp_path: Path):
    output_path = tmp_path / "index.html"

    render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "OBJECT_NOT_FOUND" in html
    assert "Marker was not found" in html


def test_dashboard_escapes_html_payload_values(tmp_path: Path):
    output_path = tmp_path / "index.html"

    render_dashboard(sample_events(), output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "<script>alert('x')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html


def test_dashboard_can_render_from_replay_json_under_tmp_path(tmp_path: Path):
    replay_path = tmp_path / "replay.json"
    output_path = tmp_path / "nested" / "dashboard.html"
    replay_path.write_text(
        """[
  {
    "event_id": "event-001",
    "task_id": "task-123",
    "correlation_id": "corr-123",
    "sequence": 1,
    "event_type": "task.completed",
    "occurred_at": "2026-07-02T12:00:00+00:00",
    "source": "valera.test",
    "mode": "simulation",
    "payload": {"status": "completed"},
    "evidence_refs": []
  }
]""",
        encoding="utf-8",
    )

    summary = render_dashboard_from_replay(replay_path, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert summary.final_status == "completed"
    assert "task-123" in html
    assert "completed" in html
