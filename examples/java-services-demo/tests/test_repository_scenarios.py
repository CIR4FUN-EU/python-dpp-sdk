from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from dpp_sdk import Dpp4Fun
from dpp_sdk.clients import (
    CreateDppResponse,
    DeleteDppResponse,
    DppHttpClientError,
    DppStatusCode,
    ReadDppIdsResponse,
)

from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.fixtures import DemoIdentity, build_complete_fixture
from dpp_java_services_demo.reporting import ScenarioStatus
from dpp_java_services_demo.repository_scenarios import (
    run_repository_scenarios,
    wait_for_repository,
)


class FakeRepositoryClient:
    def __init__(self, original: Dpp4Fun, *, health: list[bool] | None = None) -> None:
        self.original = original
        self.current = original
        self.active = False
        self.health = list(health or [True])
        self.history_reads = 0

    def health_check(self) -> bool:
        return self.health.pop(0) if self.health else True

    def create_dpp(self, dpp: Dpp4Fun) -> CreateDppResponse:
        if self.active:
            raise DppHttpClientError("conflict", 409, "{}")
        self.active = True
        self.original = dpp
        self.current = dpp
        return CreateDppResponse(dppId=dpp.dpp_id)

    def read_dpp_by_id(self, dpp_id: str) -> Dpp4Fun:
        if not self.active or dpp_id != self.current.dpp_id:
            raise DppHttpClientError("missing", 404, "{}")
        return self.current

    def read_compressed_dpp_by_id(self, dpp_id: str) -> dict[str, Any]:
        self.read_dpp_by_id(dpp_id)
        return {"dppId": dpp_id, "representation": "compressed"}

    def read_dpp_by_product_id(self, product_id: str) -> Dpp4Fun:
        if not self.active or product_id != self.current.product_id:
            raise DppHttpClientError("missing product", 404, "{}")
        return self.current

    def read_dpp_version_by_id_and_date(self, dpp_id: str, at: datetime) -> Dpp4Fun:
        assert at.tzinfo is not None
        self.read_dpp_by_id(dpp_id)
        self.history_reads += 1
        return self.original if self.history_reads == 1 else self.current

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], limit: int | None = None, cursor: str | None = None
    ) -> ReadDppIdsResponse:
        assert limit == 10 and cursor == "0"
        identifiers = [self.current.dpp_id] if self.current.product_id in product_ids else []
        return ReadDppIdsResponse(dppIdentifiers=identifiers, nextCursor=None)

    def update_dpp_by_id(self, dpp_id: str, patch: Any) -> Dpp4Fun:
        self.read_dpp_by_id(dpp_id)
        if "passportMetadata" in patch:
            raise DppHttpClientError("invalid patch", 400, "{}")
        product_name = patch["characteristics"]["productName"]
        characteristics = self.current.characteristics.with_updates(productName=product_name)
        self.current = self.current.with_updates(characteristics=characteristics)
        return self.current

    def read_data_element(self, dpp_id: str, path: str) -> Any:
        self.read_dpp_by_id(dpp_id)
        errors = {
            "characteristics.productName": 400,
            "$.characteristics.missing": 404,
            "$.billOfMaterials.materials[*]": 501,
        }
        if path in errors:
            raise DppHttpClientError("fine read error", errors[path], "{}")
        if path == "$.characteristics.productName":
            return self.current.productName
        if path == "$.billOfMaterials.materials[0].name":
            assert self.current.billOfMaterials is not None
            return self.current.billOfMaterials.materials[0].name
        raise AssertionError(path)

    def update_data_element(self, dpp_id: str, path: str, payload: Any) -> Any:
        self.read_dpp_by_id(dpp_id)
        if path == "$":
            raise DppHttpClientError("root replacement", 400, "{}")
        assert path == "$.characteristics.productName"
        characteristics = self.current.characteristics.with_updates(productName=payload)
        self.current = self.current.with_updates(characteristics=characteristics)
        return payload

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
        self.read_dpp_by_id(dpp_id)
        self.active = False
        return DeleteDppResponse(statusCode=DppStatusCode.SuccessNoContent)

    def close(self) -> None:
        pass


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image="repo",
        registry_image="registry",
        env_file=__file__,  # type: ignore[arg-type]
        startup_timeout_seconds=2.0,
        legacy=False,
    )


def test_repository_readiness_retries_functional_health_without_fixed_sleep() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    client = FakeRepositoryClient(build_complete_fixture(identity), health=[False, False, True])
    clock_values = iter((0.0, 0.1, 0.2, 0.3))
    pauses: list[float] = []

    result = wait_for_repository(
        _config(),
        client=client,
        clock=lambda: next(clock_values),
        pause=pauses.append,
        interval_seconds=0.01,
    )

    assert result.status is ScenarioStatus.PASSED
    assert pauses == [0.01, 0.01]


def test_repository_runner_covers_rep_01_through_rep_15_and_preserves_original() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    original = build_complete_fixture(identity)
    client = FakeRepositoryClient(original)

    run = run_repository_scenarios(_config(), identity, client=client)

    assert tuple(result.scenario_id for result in run.results) == tuple(
        f"REP-{index:02d}" for index in range(1, 16)
    )
    assert all(result.status is ScenarioStatus.PASSED for result in run.results)
    assert run.cleanup_warnings == ()
    assert original.productName == "CIR4FUN Demo Chair"
    assert client.active is False


def test_cleanup_failure_is_a_warning_separate_from_scenario_failure() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))

    class FailingDeleteClient(FakeRepositoryClient):
        def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
            raise DppHttpClientError("delete failed", 500, "{}")

    run = run_repository_scenarios(
        _config(),
        identity,
        client=FailingDeleteClient(build_complete_fixture(identity)),
    )

    assert any(
        result.scenario_id == "REP-11" and result.status is ScenarioStatus.FAILED
        for result in run.results
    )
    assert run.cleanup_warnings
