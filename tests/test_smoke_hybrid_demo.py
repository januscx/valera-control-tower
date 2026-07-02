from pathlib import Path

import pytest

pytest.importorskip("cv2")
pytest.importorskip("cv2.aruco")

from dashboard.render import DashboardSummary
from scripts import smoke_hybrid_demo


def test_smoke_verifier_passes_for_tmp_output_root(tmp_path: Path):
    result = smoke_hybrid_demo.run_hybrid_demo_smoke(tmp_path)

    assert result.task_id == "hybrid-fixture-task-001"
    assert result.final_status == "completed"
    assert result.event_count == 14
    assert result.replay_path == tmp_path / "data" / "runs" / result.task_id / "replay.json"
    assert result.dashboard_path == tmp_path / "data" / "runs" / result.task_id / "dashboard.html"


def test_smoke_verifier_creates_replay_and_dashboard(tmp_path: Path):
    result = smoke_hybrid_demo.run_hybrid_demo_smoke(tmp_path)

    assert result.replay_path.is_file()
    assert result.dashboard_path.is_file()


def test_smoke_verifier_confirms_evidence_files_exist(tmp_path: Path):
    result = smoke_hybrid_demo.run_hybrid_demo_smoke(tmp_path)

    assert len(result.evidence_paths) == 2
    assert any(path.name.endswith("-raw.png") for path in result.evidence_paths)
    assert any(path.name.endswith("-annotated.png") for path in result.evidence_paths)
    assert all(path.is_file() for path in result.evidence_paths)


def test_smoke_verifier_confirms_dashboard_evidence_links_and_previews(tmp_path: Path):
    result = smoke_hybrid_demo.run_hybrid_demo_smoke(tmp_path)

    html = result.dashboard_path.read_text(encoding="utf-8")
    assert 'href="../../evidence/hybrid-fixture-task-001/' in html
    assert 'src="../../evidence/hybrid-fixture-task-001/' in html
    assert 'class="evidence-preview"' in html


def test_smoke_verifier_fails_clearly_when_dashboard_preview_tags_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def render_without_previews(replay_path: Path, dashboard_path: Path) -> DashboardSummary:
        dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        dashboard_path.write_text(
            "<html><body><a href=\"../../evidence/example.png\">Open evidence file</a>"
            "task.completed</body></html>\n",
            encoding="utf-8",
        )
        return DashboardSummary(
            task_id="hybrid-fixture-task-001",
            correlation_id="corr-test",
            final_status="completed",
            event_count=14,
        )

    monkeypatch.setattr(smoke_hybrid_demo, "render_dashboard_from_replay", render_without_previews)

    with pytest.raises(RuntimeError, match="evidence preview"):
        smoke_hybrid_demo.run_hybrid_demo_smoke(tmp_path)


def test_smoke_main_prints_fail_before_reraising(monkeypatch: pytest.MonkeyPatch, capsys):
    def fail_smoke(output_root: Path):
        raise RuntimeError("demo chain broke")

    monkeypatch.setattr(smoke_hybrid_demo, "run_hybrid_demo_smoke", fail_smoke)

    with pytest.raises(RuntimeError, match="demo chain broke"):
        smoke_hybrid_demo.main()

    output = capsys.readouterr().out
    assert "FAIL: Hybrid Evidence Demo smoke verification" in output
