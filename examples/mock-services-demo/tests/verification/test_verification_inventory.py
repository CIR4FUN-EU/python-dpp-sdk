"""Inventory guards for coverage that must survive public-demo simplification."""

from dpp_mock_services_demo import controlled_scenarios, registry_scenarios, repository_scenarios
from dpp_mock_services_demo.sdk_scenarios import SCENARIOS


def test_maintained_verification_inventory_is_complete() -> None:
    assert tuple(scenario.scenario_id for scenario in SCENARIOS) == tuple(
        f"SDK-{index:02d}" for index in range(1, 18)
    )
    assert tuple(repository_scenarios._NAMES) == tuple(f"REP-{index:02d}" for index in range(1, 16))
    assert tuple(registry_scenarios._NAMES) == tuple(f"REG-{index:02d}" for index in range(1, 8))
    controlled_ids = tuple(
        result.scenario_id for result in controlled_scenarios.run_controlled_scenarios()
    )
    assert controlled_ids == (
        "REP-16",
        "REP-17",
        "REP-18",
        "REG-08",
    )
