from __future__ import annotations

import json

import pytest

from dpp_java_services_demo.__main__ import main


def test_sdk_mode_runs_all_sdk_scenarios_successfully(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["sdk"])
    output = capsys.readouterr().out

    assert exit_code == 0
    scenario_lines = [line for line in output.splitlines() if line.startswith("- SDK-")]
    assert len(scenario_lines) == 15
    assert "SDK-01" in output and "SDK-15" in output
    assert "FAILED" not in output
    assert "NOT_IMPLEMENTED" not in output


@pytest.mark.parametrize("mode", ["services", "all", "verify"])
def test_live_dependent_modes_are_truthful_and_nonzero(
    mode: str, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main([mode])
    output = capsys.readouterr().out

    assert exit_code != 0
    assert "NOT_IMPLEMENTED" in output
    assert "next implementation phase" in output
    if mode in {"all", "verify"}:
        assert "SDK-01" in output and "SDK-15" in output
    if mode == "verify":
        assert "SDK-only partial verification" in output


def test_json_output_is_structured(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["sdk", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["mode"] == "sdk"
    assert len(payload["results"]) == 15
    assert {result["status"] for result in payload["results"]} == {"PASSED"}


def test_legacy_profile_requires_explicit_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["sdk", "--env-file", "env/0.4.0.env"])
    error = capsys.readouterr().err

    assert exit_code == 2
    assert "--legacy" in error
