from __future__ import annotations

from pathlib import Path
from uuid import UUID

from dpp_sdk import Dpp4Fun
from dpp_sdk.clients import (
    CreateDppResponse,
    DeleteDppResponse,
    DppHttpClientError,
    DppStatusCode,
    RegisterDppRequest,
    RegisterDppResponse,
)

from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.fixtures import DemoIdentity
from dpp_java_services_demo.registry_scenarios import run_registry_scenarios
from dpp_java_services_demo.reporting import ScenarioStatus


class FakeRepo:
    def __init__(self) -> None:
        self.active: set[str] = set()

    def health_check(self) -> bool:
        return True

    def create_dpp(self, dpp: Dpp4Fun) -> CreateDppResponse:
        self.active.add(dpp.dpp_id)
        return CreateDppResponse(dppId=dpp.dpp_id)

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
        self.active.remove(dpp_id)
        return DeleteDppResponse(statusCode=DppStatusCode.SuccessNoContent)

    def close(self) -> None:
        pass


class FakeRegistry:
    def __init__(self, repo: FakeRepo) -> None:
        self.repo = repo
        self.registered: set[str] = set()

    def health_check(self) -> bool:
        return True

    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> RegisterDppResponse:
        if not request.uniqueProductIdentifier:
            raise DppHttpClientError("invalid request", 400, "{}")
        if request.dppApiEndpoint == "http://127.0.0.1:1":
            raise DppHttpClientError("unavailable repository", 502, "{}")
        dpp_id = request.digitalProductPassportId
        if dpp_id not in self.repo.active:
            raise DppHttpClientError("missing repository DPP", 404, "{}")
        if dpp_id in self.registered:
            raise DppHttpClientError("duplicate registration", 409, "{}")
        self.registered.add(dpp_id)
        return RegisterDppResponse(registrationId=f"registration-{dpp_id}")

    def close(self) -> None:
        pass


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image="repo",
        registry_image="registry",
        env_file=Path(__file__),
        startup_timeout_seconds=2.0,
        legacy=False,
    )


def test_registry_runner_covers_reg_01_through_reg_07_without_internal_routes() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repo = FakeRepo()
    registry = FakeRegistry(repo)

    run = run_registry_scenarios(
        _config(),
        identity,
        repo_client=repo,
        registry_client=registry,
    )

    assert tuple(result.scenario_id for result in run.results) == tuple(
        f"REG-{index:02d}" for index in range(1, 8)
    )
    assert all(result.status is ScenarioStatus.PASSED for result in run.results)
    assert run.cleanup_warnings == ()
    assert repo.active == set()


def test_registry_cleanup_failure_is_reported_as_warning() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))

    class FailingCleanupRepo(FakeRepo):
        def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
            raise DppHttpClientError("cleanup failed", 500, "{}")

    repo = FailingCleanupRepo()
    run = run_registry_scenarios(
        _config(),
        identity,
        repo_client=repo,
        registry_client=FakeRegistry(repo),
    )

    assert run.cleanup_warnings
