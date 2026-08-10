from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from dpp_java_services_demo import __main__ as cli
from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.fixtures import DemoIdentity
from dpp_java_services_demo.image_identity import (
    ImageEquivalence,
    ImageIdentityReport,
    RuntimeImageIdentity,
)
from dpp_java_services_demo.integration_scenarios import run_integration_scenarios
from dpp_java_services_demo.reporting import LiveRun, ScenarioResult, ScenarioStatus

_REAL_INSTALLED_SDK_RESULT = cli._installed_sdk_result


def test_parser_exposes_canonical_modes_and_legacy_aliases() -> None:
    choices = cli._parser()._actions[1].choices

    assert set(choices) == {"sdk", "demo", "full", "verify", "integration", "services", "all"}


@pytest.mark.parametrize(
    ("requested", "canonical", "profile"),
    (
        ("sdk", "sdk", "sdk"),
        ("demo", "demo", "demo"),
        ("full", "full", "full"),
        ("verify", "verify", "verify"),
        ("integration", "demo", "integration"),
        ("services", "full", "full"),
        ("all", "full", "all"),
    ),
)
def test_mode_resolution_preserves_legacy_behavior(
    requested: str, canonical: str, profile: str
) -> None:
    resolution = cli.resolve_mode(requested)

    assert resolution.canonical == canonical
    assert resolution.requested == requested
    assert resolution.profile == profile


def test_live_payload_omits_alias_for_canonical_mode() -> None:
    canonical = cli._annotate_live_payload({"mode": "demo"}, cli.resolve_mode("demo"))
    alias = cli._annotate_live_payload({"mode": "integration"}, cli.resolve_mode("integration"))

    assert "compatibility_alias" not in canonical
    assert alias["compatibility_alias"] == "integration"


def test_full_mode_forwards_detailed_to_its_renderer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: list[bool] = []
    monkeypatch.setattr(cli, "_report", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "has_required_failure", lambda _report: False)
    monkeypatch.setattr(
        cli,
        "_load_service_config",
        lambda _args: DemoConfig(
            "repo", "registry", "repo", "registry", Path("demo.env"), 1.0, False
        ),
    )
    monkeypatch.setattr(
        cli,
        "render_text",
        lambda _report, *, summary, detailed=False: captured.append(detailed) or "full",
    )

    assert cli.main(["full", "--detailed"]) == 0
    assert captured == [True]


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
    assert output.count("[SDK-") == 5
    assert "SDK-01" in output and "SDK-07" in output
    assert "expected_error=0" in output
    assert "FAILED" not in output
    assert "NOT_IMPLEMENTED" not in output


@pytest.mark.parametrize("arguments", (["sdk"], ["sdk", "--json"]))
def test_sdk_mode_does_not_load_service_configuration(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    def unexpected_service_configuration(*_args: object, **_kwargs: object) -> DemoConfig:
        raise AssertionError("SDK-only mode must not load service configuration")

    monkeypatch.setattr(cli, "load_config", unexpected_service_configuration)

    assert cli.main(arguments) == 0


@pytest.mark.parametrize("mode", ("all", "verify"))
def test_combined_modes_load_service_configuration_only_after_sdk_scenarios(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []

    def sdk_scenarios(_run_id: object) -> tuple[ScenarioResult, ...]:
        events.append("sdk")
        return (_passed("SDK-01", "SDK_LOCAL"),)

    def unavailable_configuration(*_args: object, **_kwargs: object) -> DemoConfig:
        events.append("configuration")
        raise ValueError("missing profile")

    monkeypatch.setattr(cli, "run_sdk_scenarios", sdk_scenarios)
    monkeypatch.setattr(cli, "load_config", unavailable_configuration)

    assert cli.main([mode]) == 2
    assert events == ["sdk", "configuration"]
    assert f"{mode} mode requires service configuration" in capsys.readouterr().err


def test_services_mode_names_missing_service_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable_configuration(*_args: object, **_kwargs: object) -> DemoConfig:
        raise ValueError("missing profile")

    monkeypatch.setattr(cli, "load_config", unavailable_configuration)

    assert cli.main(["services"]) == 2
    assert (
        "services mode requires service configuration: missing profile" in capsys.readouterr().err
    )


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


def test_integration_writes_atomic_json_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "evidence" / "integration.json"
    monkeypatch.setattr(
        cli,
        "run_integration_scenarios",
        lambda identity, config, **_kwargs: object(),
    )

    payload = {"mode": "integration", "summary": {"total": 0}}
    cli._write_json_report(report_path, payload)

    assert json.loads(report_path.read_text(encoding="utf-8"))["mode"] == "integration"
    assert not list(report_path.parent.glob("*.tmp"))


def test_integration_captures_runtime_identity_only_for_explicit_project(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured_projects: list[str] = []
    runtime_identity = RuntimeImageIdentity(
        repo_runtime_digest="sha256:repo-runtime",
        registry_runtime_digest="sha256:registry-runtime",
    )

    def capture_runtime(config: DemoConfig, *, compose_project: str) -> RuntimeImageIdentity:
        assert config.repo_image
        captured_projects.append(compose_project)
        return runtime_identity

    def integration_runner(identity: object, config: DemoConfig, **kwargs: object) -> object:
        assert kwargs["image_identity"] is runtime_identity
        return object()

    monkeypatch.setattr(cli, "capture_runtime_image_identities", capture_runtime)
    monkeypatch.setattr(cli, "run_integration_scenarios", integration_runner)
    monkeypatch.setattr(
        cli,
        "integration_payload",
        lambda _report: {"mode": "integration", "exit_outcome": "SUCCESS"},
    )

    assert cli.main(["integration", "--compose-project", "isolated-project", "--json"]) == 0
    assert captured_projects == ["isolated-project"]
    assert json.loads(capsys.readouterr().out)["mode"] == "integration"


def test_integration_blocked_readiness_writes_json_failure_and_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    blocked = run_integration_scenarios(
        DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678")),
        config=None,
    )
    report_path = tmp_path / "blocked-integration.json"
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda *_args, **_kwargs: DemoConfig(
            repo_base_url="http://localhost:18080",
            registry_base_url="http://localhost:18081",
            repo_image="repo@example",
            registry_image="registry@example",
            env_file=tmp_path / "demo.env",
            startup_timeout_seconds=2.0,
            legacy=False,
        ),
    )
    monkeypatch.setattr(cli, "run_integration_scenarios", lambda *_args, **_kwargs: blocked)

    assert cli.main(["integration", "--json", "--report-file", str(report_path)]) == 1
    console_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert console_payload == file_payload
    assert console_payload["exit_outcome"] == "FAILURE"
    assert console_payload["summary"]["blocked_steps"] == 14


def test_integration_invalid_configuration_and_missing_mode_return_parser_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad profile")),
    )

    assert cli.main(["integration"]) == 2
    assert "integration mode requires service configuration: bad profile" in capsys.readouterr().err
    with pytest.raises(SystemExit) as missing_mode:
        cli._parser().parse_args([])
    assert missing_mode.value.code == 2


def test_successful_integration_does_not_mask_a_later_verify_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "run_integration_scenarios", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "integration_payload",
        lambda _report: {"mode": "integration", "exit_outcome": "SUCCESS"},
    )

    assert cli.main(["integration", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["exit_outcome"] == "SUCCESS"

    monkeypatch.setattr(
        cli,
        "run_repository_scenarios",
        lambda _config, _identity: LiveRun(
            (
                ScenarioResult(
                    scenario_id="REP-01",
                    name="repository readiness",
                    category="LIVE_050",
                    status=ScenarioStatus.FAILED,
                    duration_seconds=0.0,
                    summary="repository unavailable",
                ),
            )
        ),
    )
    assert cli.main(["verify"]) == 1
    assert "PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED" in capsys.readouterr().out


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
    assert "IMG-01 | Runtime image digest capture | IMAGE_IDENTITY | PASSED" in output
    assert "IMG-02 | Maintained 0.5.1 identity comparison | IMAGE_IDENTITY | FAILED" in output


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
    assert len(payload["results"]) == 5
    assert payload["schema_version"] == 2
    assert payload["teaching_schema_version"] == 1
    assert payload["mode_verdict"] == "SDK_DEMONSTRATION_PASSED"
    assert payload["exit_outcome"] == "SUCCESS"
    assert {result["status"] for result in payload["results"]} == {"PASSED"}
    assert all(result["teaching"] for result in payload["results"])


def test_installed_sdk_provenance_is_bound_to_supplied_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "venv"
    site_packages = prefix / "Lib" / "site-packages"
    sdk_file = site_packages / "dpp_sdk" / "__init__.py"
    sdk_file.parent.mkdir(parents=True)
    sdk_file.write_text("", encoding="utf-8")
    wheel = tmp_path / "dpp_sdk-0.4.0-py3-none-any.whl"
    wheel.write_bytes(b"exact wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()

    class FakeDistribution:
        version = "0.4.0"

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
    exit_code = cli.main(["services", "--env-file", "env/0.4.0.env"])
    error = capsys.readouterr().err

    assert exit_code == 2
    assert "--legacy" in error
