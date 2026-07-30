"""REG-01 through REG-07 against an already-running Java registry service."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from dpp_sdk import Dpp4Fun, Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import (
    CreateDppResponse,
    DeleteDppResponse,
    DppHttpClientError,
    DppRegistryClient,
    DppRepoClient,
    RegisterDppRequest,
    RegisterDppResponse,
)

from .config import DemoConfig
from .fixtures import DemoIdentity, build_complete_fixture
from .readiness import wait_for_health
from .reporting import LiveRun, ScenarioResult, ScenarioStatus


class RegistryRepositoryClient(Protocol):
    def create_dpp(self, dpp: Dpp4Fun) -> CreateDppResponse: ...

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse: ...

    def close(self) -> None: ...


class RegistryClient(Protocol):
    def health_check(self) -> bool: ...

    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> RegisterDppResponse: ...

    def close(self) -> None: ...


_NAMES = {
    "REG-01": "Registry functional readiness",
    "REG-02": "Register repository-backed DPP",
    "REG-03": "Prove repository-backed verification",
    "REG-04": "Reject duplicate registration",
    "REG-05": "Reject missing repository DPP",
    "REG-06": "Reject unavailable repository",
    "REG-07": "Reject invalid registration request",
}


def _result(scenario_id: str, operation: Callable[[], str]) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
    except Exception as exc:  # noqa: BLE001 - live boundary records unexpected category
        return ScenarioResult(
            scenario_id=scenario_id,
            name=_NAMES[scenario_id],
            category="LIVE_050",
            status=ScenarioStatus.FAILED,
            duration_seconds=perf_counter() - started,
            summary="Live registry assertion failed",
            details=f"{type(exc).__name__}: {exc}",
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        name=_NAMES[scenario_id],
        category="LIVE_050",
        status=ScenarioStatus.PASSED,
        duration_seconds=perf_counter() - started,
        summary="Live registry assertion passed",
        details=details,
    )


def _expected_http(operation: Callable[[], object], status_code: int, context: str) -> None:
    try:
        operation()
    except DppHttpClientError as exc:
        if exc.status_code != status_code:
            raise AssertionError(
                f"{context}: expected HTTP {status_code}, got {exc.status_code}"
            ) from exc
        return
    raise AssertionError(f"{context}: expected DppHttpClientError HTTP {status_code}")


def _fail_remaining(start: int, reason: str) -> dict[str, ScenarioResult]:
    return {
        f"REG-{index:02d}": ScenarioResult(
            scenario_id=f"REG-{index:02d}",
            name=_NAMES[f"REG-{index:02d}"],
            category="LIVE_050",
            status=ScenarioStatus.FAILED,
            duration_seconds=0.0,
            summary="Required registry prerequisite failed",
            details=reason,
        )
        for index in range(start, 8)
    }


def run_registry_scenarios(
    config: DemoConfig,
    identity: DemoIdentity,
    *,
    repo_client: RegistryRepositoryClient | None = None,
    registry_client: RegistryClient | None = None,
) -> LiveRun:
    """Create, register, exercise natural negatives, and clean the repository DPP."""

    own_repo = repo_client is None
    own_registry = registry_client is None
    repo = repo_client or DppRepoClient(
        config.repo_base_url,
        Dpp4FunJsonCodec(),
        validate_dpp4fun,
    )
    registry = registry_client or DppRegistryClient(config.registry_base_url)
    fixture = build_complete_fixture(identity)
    dpp_id = fixture.dpp_id
    results: dict[str, ScenarioResult] = {}
    cleanup_warnings: list[str] = []
    active = False
    try:
        results["REG-01"] = wait_for_health(
            scenario_id="REG-01",
            name=_NAMES["REG-01"],
            client=registry,
            timeout_seconds=config.startup_timeout_seconds,
            endpoint=config.registry_base_url,
        )
        if results["REG-01"].status is not ScenarioStatus.PASSED:
            results.update(_fail_remaining(2, "REG-01 readiness failed"))
            return LiveRun(tuple(results[f"REG-{index:02d}"] for index in range(1, 8)))

        def create_repository_dpp() -> None:
            nonlocal active
            validate_dpp4fun(fixture)
            created = repo.create_dpp(fixture)
            if created.dppId != dpp_id:
                raise AssertionError(f"repository created unexpected dppId {created.dppId}")
            active = True

        try:
            create_repository_dpp()
        except Exception as exc:  # noqa: BLE001 - prerequisite becomes explicit scenario failures
            failure = f"repository create failed: {type(exc).__name__}: {exc}"
            results.update(_fail_remaining(2, failure))
            return LiveRun(tuple(results[f"REG-{index:02d}"] for index in range(1, 8)))

        request = RegisterDppRequest(
            uniqueProductIdentifier=fixture.product_id,
            digitalProductPassportId=dpp_id,
            uniqueEconomicOperatorIdentifier=identity.registry_sensitive_id,
            dppApiEndpoint=config.repo_base_url,
        )

        def register() -> str:
            response = registry.post_new_dpp_to_registry(request)
            if response.registrationId is None or not response.registrationId.strip():
                raise AssertionError("registrationId is missing or blank")
            return f"registrationId={response.registrationId}"

        results["REG-02"] = _result("REG-02", register)
        results["REG-04"] = _result(
            "REG-04",
            lambda: (
                _expected_http(
                    lambda: registry.post_new_dpp_to_registry(request),
                    409,
                    "duplicate registration",
                )
                or "duplicate registration returned HTTP 409"
            ),
        )

        missing_request = RegisterDppRequest(
            uniqueProductIdentifier=f"missing-product-{uuid4().hex}",
            digitalProductPassportId=str(uuid4()),
            uniqueEconomicOperatorIdentifier=f"missing-operator-{uuid4().hex}",
            dppApiEndpoint=config.repo_base_url,
        )
        results["REG-05"] = _result(
            "REG-05",
            lambda: (
                _expected_http(
                    lambda: registry.post_new_dpp_to_registry(missing_request),
                    404,
                    "missing repository DPP",
                )
                or "missing repository DPP returned HTTP 404"
            ),
        )

        def verification_evidence() -> str:
            if results["REG-02"].status is not ScenarioStatus.PASSED:
                raise AssertionError("successful repository-backed registration was not proven")
            if results["REG-05"].status is not ScenarioStatus.PASSED:
                raise AssertionError("missing repository DPP rejection was not proven")
            return "REG-02 success plus REG-05 HTTP 404 proves repository-backed verification"

        results["REG-03"] = _result("REG-03", verification_evidence)

        unavailable_request = RegisterDppRequest(
            uniqueProductIdentifier=f"unreachable-product-{uuid4().hex}",
            digitalProductPassportId=str(uuid4()),
            uniqueEconomicOperatorIdentifier=f"unreachable-operator-{uuid4().hex}",
            dppApiEndpoint="http://127.0.0.1:1",
        )
        results["REG-06"] = _result(
            "REG-06",
            lambda: (
                _expected_http(
                    lambda: registry.post_new_dpp_to_registry(unavailable_request),
                    502,
                    "unavailable repository",
                )
                or "container-local unreachable repository returned HTTP 502"
            ),
        )

        invalid_request = RegisterDppRequest(
            uniqueProductIdentifier="",
            digitalProductPassportId=str(uuid4()),
            uniqueEconomicOperatorIdentifier=f"invalid-operator-{uuid4().hex}",
            dppApiEndpoint=config.repo_base_url,
        )
        results["REG-07"] = _result(
            "REG-07",
            lambda: (
                _expected_http(
                    lambda: registry.post_new_dpp_to_registry(invalid_request),
                    400,
                    "invalid request",
                )
                or "blank required value returned HTTP 400"
            ),
        )
    finally:
        if active:
            try:
                repo.delete_dpp_by_id(dpp_id)
                active = False
            except Exception as exc:  # noqa: BLE001 - cleanup warning is report evidence
                cleanup_warnings.append(
                    f"registry-flow repository cleanup for {dpp_id}: {type(exc).__name__}: {exc}"
                )
        if own_registry:
            registry.close()
        if own_repo:
            repo.close()

    ordered = tuple(results[f"REG-{index:02d}"] for index in range(1, 8))
    return LiveRun(ordered, tuple(cleanup_warnings))
