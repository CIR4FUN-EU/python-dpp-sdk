from __future__ import annotations

from uuid import UUID

from dpp_mock_services_demo.reporting import ScenarioStatus
from dpp_mock_services_demo.sdk_scenarios import run_sdk_scenarios

EXPECTED_IDS = tuple(f"SDK-{index:02d}" for index in range(1, 13))


def test_sdk_runner_executes_the_final_python_capability_examples() -> None:
    results = run_sdk_scenarios(UUID("12345678-1234-5678-9234-567812345678"))

    assert tuple(result.scenario_id for result in results) == EXPECTED_IDS
    assert all(
        result.status in {ScenarioStatus.PASSED, ScenarioStatus.EXPECTED_ERROR}
        for result in results
    )
    assert all(result.category and result.name and result.summary for result in results)
    assert all(result.duration_seconds >= 0 for result in results)


def test_sdk_runner_keeps_the_short_offline_walkthrough_selectable() -> None:
    results = run_sdk_scenarios(
        UUID("12345678-1234-5678-9234-567812345678"),
        scenario_ids=("SDK-01", "SDK-02", "SDK-03", "SDK-08", "SDK-12"),
    )
    assert tuple(result.scenario_id for result in results) == (
        "SDK-01",
        "SDK-02",
        "SDK-03",
        "SDK-08",
        "SDK-12",
    )


def test_sdk_runner_captures_complete_structured_teaching_evidence() -> None:
    for result in run_sdk_scenarios(UUID("12345678-1234-5678-9234-567812345678")):
        teaching = result.teaching
        assert teaching is not None
        assert teaching.group and teaching.evidence_class and teaching.purpose
        assert teaching.input
        assert teaching.operation["public_api"] and teaching.operation["display"]
        assert teaching.expected_behavior and teaching.observed_result
        assert teaching.explanation and teaching.why_it_matters


def test_invalid_client_request_is_reported_as_expected_error() -> None:
    results = {item.scenario_id: item for item in run_sdk_scenarios()}
    assert results["SDK-12"].status is ScenarioStatus.EXPECTED_ERROR
    assert "DppMappingClientError" in results["SDK-12"].details


def test_sdk_runner_converts_uncontrolled_scenario_errors_to_failed_results(monkeypatch) -> None:
    import dpp_mock_services_demo.sdk_scenarios as scenarios

    def fail(_identity, _passport) -> str:
        raise RuntimeError("controlled test failure")

    failing = [scenarios.SCENARIOS[0]._replace(run=fail), *scenarios.SCENARIOS[1:]]
    monkeypatch.setattr(scenarios, "SCENARIOS", failing)
    result = scenarios.run_sdk_scenarios()[0]
    assert result.status is ScenarioStatus.FAILED
    assert "RuntimeError" in result.details


def test_sdk_runner_rejects_missing_teaching_metadata(monkeypatch) -> None:
    import pytest

    import dpp_mock_services_demo.sdk_scenarios as scenarios

    monkeypatch.setattr(
        scenarios,
        "SCENARIOS",
        [scenarios.SCENARIOS[0]._replace(explanation=""), *scenarios.SCENARIOS[1:]],
    )
    with pytest.raises(AssertionError, match="SDK-01 has incomplete teaching metadata"):
        scenarios.run_sdk_scenarios(UUID("12345678-1234-5678-9234-567812345678"))
