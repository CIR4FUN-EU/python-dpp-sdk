from __future__ import annotations

from pathlib import Path
from uuid import UUID

from dpp_sdk.clients import (
    DppApiClientError,
    DppStatusCode,
    RegisterDppRequest,
    RegisterDppResponse,
)

from dpp_mock_services_demo.config import DemoConfig
from dpp_mock_services_demo.fixtures import DemoIdentity
from dpp_mock_services_demo.registry_scenarios import run_registry_scenarios
from dpp_mock_services_demo.reporting import ScenarioResult, ScenarioStatus


class _Registry:
    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> RegisterDppResponse:
        self.calls += 1
        if self.calls == 2:
            raise DppApiClientError(
                "duplicate", 409, DppStatusCode.ClientResourceConflict, None, "{}"
            )
        if not request.unique_product_identifier:
            raise DppApiClientError("invalid", 400, DppStatusCode.ClientErrorBadRequest, None, "{}")
        return RegisterDppResponse(registration_id="registration-1")

    def close(self) -> None:
        self.closed = True


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image="repo",
        registry_image="registry",
        env_file=Path(__file__),
        startup_timeout_seconds=0.1,
        legacy=False,
    )


def test_registry_runner_has_no_repository_contact_assumptions(monkeypatch) -> None:
    import dpp_mock_services_demo.registry_scenarios as module

    monkeypatch.setattr(
        module,
        "wait_for_health",
        lambda **kwargs: ScenarioResult(
            kwargs["scenario_id"],
            kwargs["name"],
            "test",
            ScenarioStatus.PASSED,
            0.0,
            "ready",
            "HTTP 200",
        ),
    )
    registry = _Registry()
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    run = run_registry_scenarios(_config(), identity, registry_client=registry)

    assert tuple(item.scenario_id for item in run.results) == (
        "REG-01",
        "REG-02",
        "REG-03",
        "REG-04",
    )
    assert [item.status for item in run.results] == [
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
    ]
    assert registry.calls == 3
    assert not registry.closed
    assert run.cleanup_warnings == ()


def test_registry_client_created_by_runner_is_closed(monkeypatch) -> None:
    import dpp_mock_services_demo.registry_scenarios as module

    monkeypatch.setattr(
        module,
        "wait_for_health",
        lambda **kwargs: ScenarioResult(
            kwargs["scenario_id"],
            kwargs["name"],
            "test",
            ScenarioStatus.FAILED,
            0.0,
            "not ready",
            "HTTP 503",
        ),
    )

    # Readiness fails before registration. The runner still owns and closes its client.
    class _Client(_Registry):
        pass

    monkeypatch.setattr(module, "DppRegistryClient", lambda _url: _Client())
    result = run_registry_scenarios(_config(), DemoIdentity.from_run_id(UUID(int=1)))
    assert all(item.status is ScenarioStatus.FAILED for item in result.results)
