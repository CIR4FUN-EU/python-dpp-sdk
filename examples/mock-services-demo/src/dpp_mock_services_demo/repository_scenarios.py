"""Repository API examples using only the final generic JSON client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

import httpx
from dpp_sdk import Dpp4FunJsonCodec
from dpp_sdk.clients import (
    CreateDppResponse,
    DppApiClientError,
    DppApiResponse,
    DppClientError,
    DppRepoClient,
    DppRepresentation,
    ReadDppIdsResponse,
)

from .config import DemoConfig
from .fixtures import DemoIdentity, build_complete_fixture
from .readiness import wait_for_health
from .reporting import LiveRun, ScenarioResult, ScenarioStatus


class RepositoryClient(Protocol):
    def create_dpp(
        self, dpp: object, representation: DppRepresentation = ...
    ) -> CreateDppResponse: ...

    def read_dpp_by_id(
        self, dpp_id: str, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def read_dpp_by_product_id(
        self, product_id: str, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def read_dpp_version_by_id_and_date(
        self, dpp_id: str, date: datetime, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], limit: int | None = None, cursor: str | None = None
    ) -> ReadDppIdsResponse: ...

    def update_dpp_by_id(
        self, dpp_id: str, partial_dpp: object, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def read_data_element(
        self, dpp_id: str, element_id_path: str, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def update_data_element(
        self,
        dpp_id: str,
        element_id_path: str,
        data_element: object,
        representation: DppRepresentation = ...,
    ) -> DppApiResponse: ...

    def delete_dpp_by_id(self, dpp_id: str) -> object: ...

    def close(self) -> None: ...


_NAMES = {
    "REP-01": "Repository HTTP readiness",
    "REP-02": "Create DPP JSON",
    "REP-03": "Read DPP by identifier",
    "REP-04": "Read explicit FULL representation",
    "REP-05": "Read DPP by product identifier",
    "REP-06": "Read historical DPP by date",
    "REP-07": "Bulk product identifier lookup",
    "REP-08": "PATCH DPP JSON",
    "REP-09": "Read a data element",
    "REP-10": "PATCH a data element",
    "REP-11": "Delete DPP",
    "REP-12": "Duplicate create response",
    "REP-13": "Unknown DPP response",
    "REP-14": "Reject invalid caller JSON",
    "REP-15": "Reject blank element path",
}


def _result(scenario_id: str, operation: Callable[[], str]) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
        status = ScenarioStatus.PASSED
    except Exception as exc:  # noqa: BLE001 - capture unexpected live operation failures
        details = f"{type(exc).__name__}: {exc}"
        status = ScenarioStatus.FAILED
    return ScenarioResult(
        scenario_id,
        _NAMES[scenario_id],
        "LIVE_MOCK_IMAGE",
        status,
        perf_counter() - started,
        "Repository assertion passed"
        if status is ScenarioStatus.PASSED
        else "Repository assertion failed",
        details,
    )


def wait_for_repository(
    config: DemoConfig,
    *,
    client: httpx.Client | None = None,
    clock: Callable[[], float] | None = None,
    pause: Callable[[float], object] | None = None,
    interval_seconds: float = 0.25,
) -> ScenarioResult:
    """Wait on the repository's public HTTP health route."""
    kwargs: dict[str, object] = {
        "scenario_id": "REP-01",
        "name": _NAMES["REP-01"],
        "endpoint": config.repo_base_url,
        "timeout_seconds": config.startup_timeout_seconds,
        "client": client,
        "interval_seconds": interval_seconds,
    }
    if clock is not None:
        kwargs["clock"] = clock
    if pause is not None:
        kwargs["pause"] = pause
    return wait_for_health(**kwargs)  # type: ignore[arg-type]


def run_repository_scenarios(
    config: DemoConfig,
    identity: DemoIdentity,
    *,
    client: RepositoryClient | None = None,
    readiness_client: httpx.Client | None = None,
) -> LiveRun:
    """Exercise the supported repository routes with disposable JSON data."""
    owned = client is None
    repo = client or DppRepoClient(config.repo_base_url)
    fixture = build_complete_fixture(identity)
    codec = Dpp4FunJsonCodec()
    wire = json.loads(codec.to_json(fixture))
    dpp_id, product_id = str(identity.dpp_id), identity.product_id
    results: dict[str, ScenarioResult] = {}
    active = False
    cleanup_warnings: list[str] = []
    try:
        results["REP-01"] = wait_for_repository(config, client=readiness_client)
        if results["REP-01"].status is not ScenarioStatus.PASSED:
            for index in range(2, 16):
                scenario_id = f"REP-{index:02d}"
                results[scenario_id] = ScenarioResult(
                    scenario_id,
                    _NAMES[scenario_id],
                    "LIVE_MOCK_IMAGE",
                    ScenarioStatus.SKIPPED,
                    0.0,
                    "Blocked by readiness",
                    "REP-01 did not return HTTP success",
                )
            return LiveRun(tuple(results[f"REP-{index:02d}"] for index in range(1, 16)))

        def create() -> str:
            nonlocal active
            response = repo.create_dpp(wire, DppRepresentation.FULL)
            if response.digital_product_passport_id != dpp_id:
                raise AssertionError("create response identifier differs from submitted JSON")
            active = True
            return f"digital_product_passport_id={dpp_id}"

        results["REP-02"] = _result("REP-02", create)

        def read_full(representation: DppRepresentation) -> str:
            response = repo.read_dpp_by_id(dpp_id, representation)
            if not isinstance(response.payload, dict):
                raise AssertionError("repository response payload is not a JSON object")
            if response.payload.get("digitalProductPassportId") != dpp_id:
                raise AssertionError("repository response has a different DPP identifier")
            if representation is DppRepresentation.FULL and response.payload != wire:
                raise AssertionError("repository JSON differs from submitted document")
            return f"representation={representation.value}; JSON fields={len(response.payload)}"

        results["REP-03"] = _result("REP-03", lambda: read_full(DppRepresentation.COMPRESSED))
        results["REP-04"] = _result("REP-04", lambda: read_full(DppRepresentation.FULL))
        results["REP-05"] = _result(
            "REP-05",
            lambda: _check_payload_identity(repo.read_dpp_by_product_id(product_id), dpp_id),
        )
        results["REP-06"] = _result(
            "REP-06",
            lambda: _check_payload_identity(
                repo.read_dpp_version_by_id_and_date(
                    dpp_id, datetime.now(UTC), DppRepresentation.FULL
                ),
                dpp_id,
            ),
        )

        def bulk() -> str:
            response = repo.read_dpp_ids_by_product_ids([product_id], limit=10, cursor="0")
            if dpp_id not in (response.dpp_identifiers or []):
                raise AssertionError("bulk response omitted created DPP identifier")
            return f"dpp_identifiers={response.dpp_identifiers!r}"

        results["REP-07"] = _result("REP-07", bulk)
        results["REP-08"] = _result(
            "REP-08",
            lambda: _check_payload_identity(
                repo.update_dpp_by_id(dpp_id, {"dppStatus": "active"}, DppRepresentation.FULL),
                dpp_id,
            ),
        )
        characteristics_index = next(
            index
            for index, element in enumerate(wire["elements"])
            if element["elementId"] == "characteristics"
        )
        characteristics = wire["elements"][characteristics_index]
        color_index = next(
            index
            for index, element in enumerate(characteristics["elements"])
            if element["elementId"] == "color"
        )
        color_element = characteristics["elements"][color_index]
        color_path = f"$.elements[{characteristics_index}].elements[{color_index}]"

        results["REP-09"] = _result(
            "REP-09",
            lambda: _check_element(
                repo.read_data_element(dpp_id, color_path, DppRepresentation.FULL)
            ),
        )
        results["REP-10"] = _result(
            "REP-10",
            lambda: _check_element(
                repo.update_data_element(
                    dpp_id,
                    color_path,
                    {**color_element, "value": "green"},
                    DppRepresentation.FULL,
                )
            ),
        )
        results["REP-12"] = _expected_failure(
            "REP-12", lambda: repo.create_dpp(wire, DppRepresentation.FULL)
        )
        results["REP-13"] = _expected_failure(
            "REP-13", lambda: repo.read_dpp_by_id("missing-" + identity.run_id.hex)
        )
        results["REP-14"] = _expected_failure(
            "REP-14",
            lambda: repo.create_dpp(None),  # type: ignore[arg-type]
        )
        results["REP-15"] = _expected_failure("REP-15", lambda: repo.read_data_element(dpp_id, " "))

        def delete() -> str:
            nonlocal active
            repo.delete_dpp_by_id(dpp_id)
            active = False
            try:
                repo.read_dpp_by_id(dpp_id)
            except DppApiClientError:
                return "delete completed; post-delete read returned API not found"
            raise AssertionError("deleted DPP remained readable")

        results["REP-11"] = _result("REP-11", delete)
    finally:
        if active:
            try:
                repo.delete_dpp_by_id(dpp_id)
            except Exception as exc:  # noqa: BLE001 - retain cleanup diagnostic
                cleanup_warnings.append(f"repository cleanup failed: {type(exc).__name__}: {exc}")
        if owned:
            repo.close()
    return LiveRun(
        tuple(results[f"REP-{index:02d}"] for index in range(1, 16)), tuple(cleanup_warnings)
    )


def _check_payload_identity(response: DppApiResponse, expected: str) -> str:
    payload = response.payload
    if not isinstance(payload, dict) or payload.get("digitalProductPassportId") != expected:
        raise AssertionError("response payload has an unexpected digitalProductPassportId")
    return f"digital_product_passport_id={expected}"


def _check_element(response: DppApiResponse) -> str:
    if response.payload is None:
        raise AssertionError("element response has no payload")
    return "data element response contains JSON payload"


def _expected_failure(scenario_id: str, operation: Callable[[], object]) -> ScenarioResult:
    started = perf_counter()
    try:
        operation()
    except (DppClientError, ValueError, TypeError) as exc:
        return ScenarioResult(
            scenario_id,
            _NAMES[scenario_id],
            "LIVE_MOCK_IMAGE",
            ScenarioStatus.EXPECTED_ERROR,
            perf_counter() - started,
            "Expected client boundary error",
            type(exc).__name__,
        )
    return ScenarioResult(
        scenario_id,
        _NAMES[scenario_id],
        "LIVE_MOCK_IMAGE",
        ScenarioStatus.FAILED,
        perf_counter() - started,
        "Expected an error",
        "operation unexpectedly succeeded",
    )
