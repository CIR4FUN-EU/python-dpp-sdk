"""Shared pytest fixtures (port of TestDataFactory / CoreTestDataFactory)."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    try:
        parser.addoption(
            "--run-mock-services",
            action="store_true",
            default=False,
            help=(
                "run integration tests against already-running Mock "
                "repository and registry services"
            ),
        )
    except ValueError as exc:
        if "--run-mock-services" not in str(exc):
            raise


@pytest.fixture(autouse=True)
def require_mock_services_for_integration(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> None:
    """Block every integration-marked test before it can construct a live client."""
    if request.node.get_closest_marker("integration") and not pytestconfig.getoption(
        "--run-mock-services"
    ):
        pytest.skip("requires --run-mock-services and running mock services")
