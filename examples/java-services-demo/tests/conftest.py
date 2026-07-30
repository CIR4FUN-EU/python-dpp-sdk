from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-java-services",
        action="store_true",
        default=False,
        help="run tests against already-running Java repository and registry services",
    )


@pytest.fixture
def require_java_services(pytestconfig: pytest.Config) -> None:
    if not pytestconfig.getoption("--run-java-services"):
        pytest.skip("requires --run-java-services and running Java services")
