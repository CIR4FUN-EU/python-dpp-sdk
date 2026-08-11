"""Explicit opt-in execution of the complete maintained live contract matrix."""

from uuid import uuid4

import pytest

from dpp_mock_services_demo.config import load_config
from dpp_mock_services_demo.fixtures import DemoIdentity
from dpp_mock_services_demo.registry_scenarios import run_registry_scenarios
from dpp_mock_services_demo.reporting import ScenarioStatus
from dpp_mock_services_demo.repository_scenarios import run_repository_scenarios


@pytest.mark.integration
def test_complete_repository_and_registry_live_contract_matrix() -> None:
    config = load_config()
    repository = run_repository_scenarios(config, DemoIdentity.from_run_id(uuid4()))
    registry = run_registry_scenarios(config, DemoIdentity.from_run_id(uuid4()))

    assert tuple(result.scenario_id for result in repository.results) == tuple(
        f"REP-{index:02d}" for index in range(1, 16)
    )
    assert tuple(result.scenario_id for result in registry.results) == tuple(
        f"REG-{index:02d}" for index in range(1, 8)
    )
    assert all(result.status is ScenarioStatus.PASSED for result in repository.results)
    assert all(result.status is ScenarioStatus.PASSED for result in registry.results)
    assert repository.cleanup_warnings == ()
    assert registry.cleanup_warnings == ()
