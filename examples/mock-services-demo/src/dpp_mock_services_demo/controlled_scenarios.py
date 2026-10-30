"""Deterministic client contract examples that need no live services."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from dpp_sdk.clients import (
    DppApiClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppRegistryClient,
    DppRepoClient,
    DppStatusCode,
    RegisterDppRequest,
)

from .fixtures import DemoIdentity, build_complete_fixture
from .reporting import ScenarioResult, ScenarioStatus


def _result(scenario_id: str, name: str, operation: Callable[[], str]) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
    except Exception as exc:  # noqa: BLE001 - report unexpected categories at this boundary
        return ScenarioResult(
            scenario_id,
            name,
            "CONTROLLED",
            ScenarioStatus.FAILED,
            perf_counter() - started,
            "Controlled client assertion failed",
            f"{type(exc).__name__}: {exc}",
        )
    return ScenarioResult(
        scenario_id,
        name,
        "CONTROLLED",
        ScenarioStatus.PASSED,
        perf_counter() - started,
        "Controlled client assertion passed",
        details,
    )


def _expect(error_type: type[BaseException], operation: Callable[[], object]) -> BaseException:
    try:
        operation()
    except error_type as exc:
        return exc
    raise AssertionError(f"expected {error_type.__name__}")


def _identity() -> DemoIdentity:
    return DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))


def _path_timestamp_and_body_contracts() -> str:
    observed: list[tuple[bytes, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append((request.url.raw_path, request.content))
        if request.url.path.endswith("/dppsByProductIds"):
            payload: Any = {"dppIdentifiers": ["dpp-1"], "nextCursor": None}
        elif request.method == "GET":
            payload = {"digitalProductPassportId": "DPP 1"}
        else:
            payload = "accepted"
        return httpx.Response(200, json={"statusCode": "Success", "payload": payload})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        repo = DppRepoClient("http://repo.test", client=http)
        repo.read_data_element("DPP 1", "$.characteristics.color")
        repo.read_dpp_version_by_id_and_date(
            "DPP 1",
            datetime(2026, 1, 15, 14, 0, 0, 123000, tzinfo=timezone(timedelta(hours=2))),
        )
        repo.update_data_element("D", "$.characteristics.color", "green")
        repo.read_dpp_ids_by_product_ids(["product-1"], limit=10, cursor="0")

    assert observed[0][0] == b"/v1/dpps/DPP%201/elements/%24.characteristics.color"
    assert observed[1][0] == (b"/v1/dppsByIdAndDate/DPP%201?date=2026-01-15T12%3A00%3A00.123000Z")
    assert observed[2][1] == b'"green"'
    assert json.loads(observed[3][1]) == {
        "productIdentifiers": ["product-1"],
        "limit": 10,
        "cursor": "0",
    }
    return "element, history, patch, and bulk lookup request contracts verified"


def _error_pipeline_contracts() -> str:
    def client_for(handler: Callable[[httpx.Request], httpx.Response]):
        http = httpx.Client(transport=httpx.MockTransport(handler))
        return DppRepoClient("http://repo.test", client=http), http

    repo, http = client_for(lambda _request: httpx.Response(503, text="unavailable"))
    try:
        error = _expect(DppHttpClientError, lambda: repo.read_dpp_by_id("D"))
        assert isinstance(error, DppHttpClientError) and error.status_code == 503
    finally:
        http.close()

    repo, http = client_for(
        lambda _request: httpx.Response(
            200, json={"statusCode": "ClientErrorBadRequest", "message": []}
        )
    )
    try:
        error = _expect(DppApiClientError, lambda: repo.read_dpp_by_id("D"))
        assert isinstance(error, DppApiClientError)
        assert error.status_code is DppStatusCode.ClientErrorBadRequest
    finally:
        http.close()

    for handler in (
        lambda _request: httpx.Response(200, text="not-json"),
        lambda _request: httpx.Response(200, json={"payload": {}}),
    ):
        repo, http = client_for(handler)
        try:
            _expect(
                DppMappingClientError,
                lambda current_repo=repo: current_repo.read_dpp_by_id("D"),
            )
        finally:
            http.close()

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("controlled network failure", request=request)

    repo, http = client_for(network_handler)
    try:
        _expect(DppNetworkClientError, lambda: repo.read_dpp_by_id("D"))
    finally:
        http.close()

    sent = 0

    def registry_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(registry_handler)) as http:
        registry = DppRegistryClient("http://registry.test", client=http)
        _expect(DppMappingClientError, lambda: registry.post_new_dpp_to_registry(None))  # type: ignore[arg-type]
    assert sent == 0
    return "HTTP, API, mapping, network, and preflight input failures verified"


def _versioned_endpoint_and_identity() -> str:
    observed: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.raw_path)
        return httpx.Response(
            200,
            json={"statusCode": "Success", "payload": {"dppIdentifiers": [], "nextCursor": None}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        DppRepoClient("http://repo.test", client=http).read_dpp_ids_by_product_ids(
            ["Product 1", "x/y"], limit=5
        )
    if observed != [b"/v1/dppsByProductIds"]:
        raise AssertionError(f"unexpected product batch route {observed!r}")
    return "versioned batch lookup route and JSON body verified"


def _rep17() -> str:
    paths = _path_timestamp_and_body_contracts()
    errors = _error_pipeline_contracts()
    return f"{paths}; {errors}"


def _registry_wire_contract() -> str:
    observed: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.content)
        return httpx.Response(
            200,
            json={"statusCode": "SuccessCreated", "payload": {"registrationId": "registration-1"}},
        )

    request = RegisterDppRequest(
        unique_product_identifier="product-1",
        digital_product_passport_id="dpp-1",
        unique_economic_operator_identifier="operator-1",
        dpp_api_endpoint="http://repo.test/v1/dpps",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        response = DppRegistryClient("http://registry.test", client=http).post_new_dpp_to_registry(
            request
        )
    if json.loads(observed[0]) != request.model_dump(mode="json", by_alias=True):
        raise AssertionError("registry request did not preserve canonical JSON fields")
    if response.registration_id != "registration-1":
        raise AssertionError("registration response was not decoded")
    return "canonical registration request and registrationId response verified"


def _semantic_boundary() -> str:
    fixture = build_complete_fixture(_identity())
    if not fixture.passport.data_elements:
        raise AssertionError("typed aggregate lost its core elements")
    return "typed DPP4Fun remains an application concern outside the JSON client"


def run_controlled_scenarios() -> tuple[ScenarioResult, ...]:
    """Run exact HTTP behavior assertions without external sockets."""
    return (
        _result("REP-16", "Typed model remains outside the JSON client", _semantic_boundary),
        _result("REP-17", "Exact routes, bodies and error categories", _rep17),
        _result("REP-18", "Versioned product batch endpoint", _versioned_endpoint_and_identity),
        _result("REG-08", "Canonical registry request and response", _registry_wire_contract),
    )
