from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the live opt-in when nested tests run independently.

    Root-plus-nested collection also loads the root conftest, which already owns
    this option. Pytest rejects a duplicate registration in that one combined
    invocation, so leave the existing compatible option in place.
    """
    try:
        parser.addoption(
            "--run-mock-services",
            action="store_true",
            default=False,
            help="run tests against already-running repository and registry services",
        )
    except ValueError as exc:
        if "--run-mock-services" not in str(exc):
            raise


@pytest.fixture(autouse=True)
def require_mock_services_for_integration(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> None:
    """Block every integration-marked test before it can load service configuration."""
    if request.node.get_closest_marker("integration") and not pytestconfig.getoption(
        "--run-mock-services"
    ):
        pytest.skip("requires --run-mock-services and running mock services")


@pytest.fixture
def require_mock_services(pytestconfig: pytest.Config) -> None:
    if not pytestconfig.getoption("--run-mock-services"):
        pytest.skip("requires --run-mock-services and running mock services")
