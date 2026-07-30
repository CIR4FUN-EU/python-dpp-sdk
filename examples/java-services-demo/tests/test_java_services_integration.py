from __future__ import annotations

from uuid import uuid4

import pytest

from dpp_java_services_demo.config import load_config
from dpp_java_services_demo.fixtures import DemoIdentity
from dpp_java_services_demo.reporting import ScenarioStatus
from dpp_java_services_demo.repository_scenarios import run_repository_scenarios

pytestmark = pytest.mark.integration


def test_repository_scenarios_against_published_java_image(
    require_java_services: None,
) -> None:
    run = run_repository_scenarios(load_config(), DemoIdentity.from_run_id(uuid4()))

    failures = [result for result in run.results if result.status is not ScenarioStatus.PASSED]
    assert failures == [], failures
    assert run.cleanup_warnings == ()
