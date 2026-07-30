from __future__ import annotations

import json
from pathlib import Path

import pytest

from dpp_java_services_demo import __main__ as cli
from dpp_java_services_demo.image_identity import ImageEquivalence, ImageIdentityReport
from dpp_java_services_demo.reporting import LiveRun, ScenarioResult, ScenarioStatus


def _passed(scenario_id: str, category: str) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        name=f"{scenario_id} test",
        category=category,
        status=ScenarioStatus.PASSED,
        duration_seconds=0.01,
        summary="passed",
    )


@pytest.fixture(autouse=True)
def stub_live_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_repository_scenarios",
        lambda _config, _identity: LiveRun((_passed("REP-01", "LIVE_050"),)),
    )
    monkeypatch.setattr(
        cli,
        "run_registry_scenarios",
        lambda _config, _identity: LiveRun((_passed("REG-01", "LIVE_050"),)),
    )
    monkeypatch.setattr(
        cli,
        "capture_image_identities",
        lambda _config: ImageIdentityReport(
            repo_runtime_digest="sha256:repo",
            registry_runtime_digest="sha256:registry",
            maintained_repo_digest="sha256:repo",
            maintained_registry_digest="sha256:registry",
            equivalence=ImageEquivalence.SAME_BUILD,
        ),
    )
    monkeypatch.setattr(cli, "_git_commit", lambda _start: "test-commit")
    monkeypatch.setattr(
        cli,
        "_installed_sdk_result",
        lambda _config: _passed("PKG-01", "PACKAGING"),
    )


def test_sdk_mode_runs_all_sdk_scenarios_successfully(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["sdk"])
    output = capsys.readouterr().out

    assert exit_code == 0
    scenario_lines = [line for line in output.splitlines() if line.startswith("- SDK-")]
    assert len(scenario_lines) == 15
    assert "SDK-01" in output and "SDK-15" in output
    assert "FAILED" not in output
    assert "NOT_IMPLEMENTED" not in output


@pytest.mark.parametrize(
    ("mode", "expected_ids"),
    [
        ("services", ("REP-01", "REG-01")),
        ("all", ("SDK-01", "REP-01", "REG-01")),
        ("verify", ("SDK-01", "REP-16", "REG-08", "REP-01", "REG-01", "IMG-01")),
    ],
)
def test_live_modes_compose_the_approved_scenario_classes(
    mode: str,
    expected_ids: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([mode])
    output = capsys.readouterr().out

    assert exit_code == 0
    for scenario_id in expected_ids:
        assert scenario_id in output
    assert "NOT_IMPLEMENTED" not in output


def test_verify_writes_atomic_json_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = tmp_path / "evidence" / "report.json"

    exit_code = cli.main(["verify", "--report-file", str(report_path)])
    console = capsys.readouterr().out
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED" in console
    assert payload["verdict"] == "PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED"
    assert payload["image_equivalence"] == "SAME_BUILD"
    assert payload["python_repo_commit"] == "test-commit"
    assert not list(report_path.parent.glob("*.tmp"))


def test_maintained_failure_is_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "run_repository_scenarios",
        lambda _config, _identity: LiveRun(
            (
                ScenarioResult(
                    scenario_id="REP-01",
                    name="readiness",
                    category="LIVE_050",
                    status=ScenarioStatus.FAILED,
                    duration_seconds=0,
                    summary="not ready",
                ),
            )
        ),
    )

    assert cli.main(["verify"]) == 1
    assert "PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED" in capsys.readouterr().out


def test_legacy_failure_is_informational(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "run_repository_scenarios",
        lambda _config, _identity: LiveRun(
            (
                ScenarioResult(
                    scenario_id="REP-01",
                    name="readiness",
                    category="LEGACY_040",
                    status=ScenarioStatus.FAILED,
                    duration_seconds=0,
                    summary="legacy difference",
                ),
            )
        ),
    )

    exit_code = cli.main(
        ["verify", "--env-file", "env/0.4.0.env", "--legacy"],
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "LEGACY_COMPATIBILITY_FAILED" in output
    assert "LEGACY_040" in output


def test_json_output_is_structured(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["sdk", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["mode"] == "sdk"
    assert len(payload["results"]) == 15
    assert {result["status"] for result in payload["results"]} == {"PASSED"}


def test_legacy_profile_requires_explicit_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["sdk", "--env-file", "env/0.4.0.env"])
    error = capsys.readouterr().err

    assert exit_code == 2
    assert "--legacy" in error
