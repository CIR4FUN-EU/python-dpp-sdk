from __future__ import annotations

from uuid import UUID

from dpp_java_services_demo.reporting import ScenarioStatus
from dpp_java_services_demo.sdk_scenarios import run_sdk_scenarios

EXPECTED_IDS = tuple(f"SDK-{index:02d}" for index in range(1, 18))


def test_sdk_runner_executes_the_approved_capability_matrix() -> None:
    results = run_sdk_scenarios(UUID("12345678-1234-5678-9234-567812345678"))

    assert tuple(result.scenario_id for result in results) == EXPECTED_IDS
    assert all(
        result.status in {ScenarioStatus.PASSED, ScenarioStatus.EXPECTED_ERROR}
        for result in results
    )
    assert all(result.category for result in results)
    assert all(result.name for result in results)
    assert all(result.summary for result in results)
    assert all(result.duration_seconds >= 0 for result in results)


def test_expected_negative_contracts_are_reported_as_expected_errors() -> None:
    results = {
        result.scenario_id: result
        for result in run_sdk_scenarios(UUID("12345678-1234-5678-9234-567812345678"))
    }

    negative_scenarios = (
        "SDK-04",
        "SDK-05",
        "SDK-08",
        "SDK-10",
        "SDK-11",
        "SDK-12",
        "SDK-13",
        "SDK-14",
        "SDK-16",
    )
    for scenario_id in negative_scenarios:
        assert results[scenario_id].status is ScenarioStatus.EXPECTED_ERROR
        assert results[scenario_id].details


def test_sdk_runner_converts_an_uncontrolled_scenario_error_to_failed_result(
    monkeypatch,
) -> None:
    import dpp_java_services_demo.sdk_scenarios as scenarios

    def fail(_context) -> str:
        raise RuntimeError("controlled test failure")

    failing_scenarios = [
        scenarios.SCENARIOS[0]._replace(run=fail),
        *scenarios.SCENARIOS[1:],
    ]
    monkeypatch.setattr(scenarios, "SCENARIOS", failing_scenarios)

    result = scenarios.run_sdk_scenarios()[0]

    assert result.status is ScenarioStatus.FAILED
    assert "RuntimeError" in result.details
