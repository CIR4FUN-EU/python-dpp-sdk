"""Registration endpoint examples for an already-running Mock registry."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from dpp_sdk.clients import (
    DppApiClientError,
    DppHttpClientError,
    DppRegistryClient,
    RegisterDppRequest,
)

from .config import DemoConfig
from .fixtures import DemoIdentity
from .readiness import wait_for_health
from .reporting import LiveRun, ScenarioResult, ScenarioStatus


class RegistryClient(Protocol):
    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> object: ...

    def close(self) -> None: ...


_NAMES = {
    "REG-01": "Registry HTTP readiness",
    "REG-02": "Register DPP JSON request",
    "REG-03": "Reject duplicate registration",
    "REG-04": "Reject invalid registration request",
}


def _result(scenario_id: str, operation: Callable[[], str]) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
    except Exception as exc:  # noqa: BLE001 - report live boundary errors by category
        return ScenarioResult(
            scenario_id,
            _NAMES[scenario_id],
            "LIVE_MOCK_IMAGE",
            ScenarioStatus.FAILED,
            perf_counter() - started,
            "Live registry assertion failed",
            f"{type(exc).__name__}: {exc}",
        )
    return ScenarioResult(
        scenario_id,
        _NAMES[scenario_id],
        "LIVE_MOCK_IMAGE",
        ScenarioStatus.PASSED,
        perf_counter() - started,
        "Live registry assertion passed",
        details,
    )


def _expect_http(operation: Callable[[], object], status: int, context: str) -> None:
    try:
        operation()
    except (DppHttpClientError, DppApiClientError) as exc:
        actual_status = exc.http_status if isinstance(exc, DppApiClientError) else exc.status_code
        if actual_status == status:
            return
        raise AssertionError(f"{context}: expected HTTP {status}, got {actual_status}") from exc
    raise AssertionError(f"{context}: expected HTTP {status}")


def _request(identity: DemoIdentity, config: DemoConfig) -> RegisterDppRequest:
    return RegisterDppRequest(
        unique_product_identifier=identity.product_id,
        digital_product_passport_id=str(identity.dpp_id),
        unique_economic_operator_identifier=identity.registry_sensitive_id,
        dpp_api_endpoint=f"{config.repo_base_url.rstrip('/')}/v1/dpps",
    )


def run_registry_scenarios(
    config: DemoConfig,
    identity: DemoIdentity,
    *,
    registry_client: RegistryClient | None = None,
    readiness_client=None,
) -> LiveRun:
    """Exercise registry registration without asserting repository lookup behavior."""
    owned = registry_client is None
    registry = registry_client or DppRegistryClient(config.registry_base_url)
    request = _request(identity, config)
    results: dict[str, ScenarioResult] = {}
    try:
        results["REG-01"] = wait_for_health(
            scenario_id="REG-01",
            name=_NAMES["REG-01"],
            endpoint=config.registry_base_url,
            timeout_seconds=config.startup_timeout_seconds,
            client=readiness_client,
        )
        if results["REG-01"].status is not ScenarioStatus.PASSED:
            for scenario_id in ("REG-02", "REG-03", "REG-04"):
                results[scenario_id] = ScenarioResult(
                    scenario_id,
                    _NAMES[scenario_id],
                    "LIVE_MOCK_IMAGE",
                    ScenarioStatus.FAILED,
                    0,
                    "Registry readiness prerequisite failed",
                    "REG-01 failed",
                )
            return LiveRun(tuple(results[f"REG-{index:02d}"] for index in range(1, 5)))

        registration_id = ""

        def register() -> str:
            nonlocal registration_id
            response = registry.post_new_dpp_to_registry(request)
            registration_id = response.registration_id or ""
            if not registration_id.strip():
                raise AssertionError("registrationId is missing or blank")
            return f"registration_id={registration_id}"

        results["REG-02"] = _result("REG-02", register)
        if results["REG-02"].status is ScenarioStatus.PASSED:
            results["REG-03"] = _result(
                "REG-03",
                lambda: (
                    _expect_http(
                        lambda: registry.post_new_dpp_to_registry(request),
                        409,
                        "duplicate registration",
                    )
                    or "duplicate request returned HTTP 409"
                ),
            )
        else:
            results["REG-03"] = ScenarioResult(
                "REG-03",
                _NAMES["REG-03"],
                "LIVE_MOCK_IMAGE",
                ScenarioStatus.FAILED,
                0,
                "Registration prerequisite failed",
                "REG-02 did not register",
            )

        invalid_request = request.model_copy(update={"unique_product_identifier": ""})
        results["REG-04"] = _result(
            "REG-04",
            lambda: (
                _expect_http(
                    lambda: registry.post_new_dpp_to_registry(invalid_request),
                    400,
                    "blank required request field",
                )
                or "invalid request returned HTTP 400"
            ),
        )
    finally:
        if owned:
            registry.close()
    return LiveRun(tuple(results[f"REG-{index:02d}"] for index in range(1, 5)))
