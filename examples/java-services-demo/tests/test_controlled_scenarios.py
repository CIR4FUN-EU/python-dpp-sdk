from __future__ import annotations

from dpp_java_services_demo.controlled_scenarios import run_controlled_scenarios
from dpp_java_services_demo.reporting import ScenarioStatus


def test_controlled_runner_covers_only_approved_non_live_contracts() -> None:
    results = run_controlled_scenarios()

    assert tuple(result.scenario_id for result in results) == (
        "REP-16",
        "REP-17",
        "REP-18",
        "REG-08",
    )
    assert all(result.category == "CONTROLLED" for result in results)
    assert all(result.status is ScenarioStatus.PASSED for result in results)
    assert all(result.details for result in results)
