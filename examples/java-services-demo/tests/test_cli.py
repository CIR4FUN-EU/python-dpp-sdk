from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dpp_java_services_demo import __main__ as cli
from dpp_java_services_demo.image_identity import ImageEquivalence, ImageIdentityReport
from dpp_java_services_demo.reporting import LiveRun, ScenarioResult, ScenarioStatus

_REAL_INSTALLED_SDK_RESULT = cli._installed_sdk_result


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
        lambda _config, *, compose_project: ImageIdentityReport(
            repo_container_id="repo-container",
            registry_container_id="registry-container",
            repo_container_image_id="sha256:repo-image",
            registry_container_image_id="sha256:registry-image",
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
        lambda _config, _sdk_wheel: _passed("PKG-01", "PACKAGING"),
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


def test_different_maintained_build_blocks_pinned_verification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "capture_image_identities",
        lambda _config, *, compose_project: ImageIdentityReport(
            repo_container_id="repo-container",
            registry_container_id="registry-container",
            repo_container_image_id="sha256:repo-image",
            registry_container_image_id="sha256:registry-image",
            repo_runtime_digest="sha256:repo",
            registry_runtime_digest="sha256:registry",
            maintained_repo_digest="sha256:new-repo",
            maintained_registry_digest="sha256:new-registry",
            equivalence=ImageEquivalence.DIFFERENT_BUILD,
        ),
    )

    assert cli.main(["verify", "--compose-project", "test-project"]) == 1
    output = capsys.readouterr().out
    assert "DIFFERENT_BUILD" in output
    assert "PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED" in output


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


def test_installed_sdk_provenance_is_bound_to_supplied_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "venv"
    site_packages = prefix / "Lib" / "site-packages"
    sdk_file = site_packages / "dpp_sdk" / "__init__.py"
    sdk_file.parent.mkdir(parents=True)
    sdk_file.write_text("", encoding="utf-8")
    wheel = tmp_path / "dpp_sdk-0.2.1-py3-none-any.whl"
    wheel.write_bytes(b"exact wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()

    class FakeDistribution:
        version = "0.2.1"

        def locate_file(self, _path: str) -> Path:
            return site_packages

        def read_text(self, _name: str) -> str:
            return json.dumps({"archive_info": {"hashes": {"sha256": digest}}})

    monkeypatch.setattr(cli.sys, "prefix", str(prefix))
    monkeypatch.setattr(cli.dpp_sdk, "__file__", str(sdk_file))
    monkeypatch.setattr(cli, "distribution", lambda _name: FakeDistribution())

    result = _REAL_INSTALLED_SDK_RESULT(cli.load_config(), wheel)

    assert result.status is ScenarioStatus.PASSED
    assert digest in result.details

    wheel.write_bytes(b"different artifact")
    result = _REAL_INSTALLED_SDK_RESULT(cli.load_config(), wheel)
    assert result.status is ScenarioStatus.FAILED


def test_legacy_profile_requires_explicit_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["sdk", "--env-file", "env/0.4.0.env"])
    error = capsys.readouterr().err

    assert exit_code == 2
    assert "--legacy" in error
