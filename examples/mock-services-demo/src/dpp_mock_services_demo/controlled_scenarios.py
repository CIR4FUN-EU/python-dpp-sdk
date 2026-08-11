"""Deterministic public-client contracts that are unsafe or impossible to induce live."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from dpp_sdk import Dpp4FunJsonCodec, OrganizationRole, to_json, validate_dpp4fun
from dpp_sdk.clients import (
    DppApiClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppRegistryClient,
    DppRepoClient,
    DppValidationClientError,
    RegisterDppRequest,
)

from .fixtures import DemoIdentity, build_complete_fixture
from .reporting import ScenarioResult, ScenarioStatus


def _result(scenario_id: str, name: str, operation: Callable[[], str]) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
    except Exception as exc:  # noqa: BLE001 - controlled boundary records unexpected category
        return ScenarioResult(
            scenario_id=scenario_id,
            name=name,
            category="CONTROLLED",
            status=ScenarioStatus.FAILED,
            duration_seconds=perf_counter() - started,
            summary="Controlled client assertion failed",
            details=f"{type(exc).__name__}: {exc}",
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        name=name,
        category="CONTROLLED",
        status=ScenarioStatus.PASSED,
        duration_seconds=perf_counter() - started,
        summary="Controlled client assertion passed",
        details=details,
    )


def _expect(
    error_type: type[BaseException],
    operation: Callable[[], object],
    *,
    cause_type: type[BaseException] | None = None,
) -> BaseException:
    try:
        operation()
    except error_type as exc:
        if cause_type is not None and not isinstance(exc.__cause__, cause_type):
            actual = type(exc.__cause__).__name__ if exc.__cause__ is not None else "None"
            raise AssertionError(f"expected cause {cause_type.__name__}, got {actual}") from exc
        return exc
    raise AssertionError(f"expected {error_type.__name__}")


def _identity() -> DemoIdentity:
    return DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))


def _rep_16() -> str:
    fixture = build_complete_fixture(_identity())
    supplier = fixture.supplier
    assert supplier is not None
    invalid_supplier = supplier.with_updates(role=OrganizationRole.MANUFACTURER)
    invalid_nameplate = fixture.nameplate.with_updates(supplier=invalid_supplier)
    invalid = fixture.with_updates(
        coreDpp=fixture.coreDpp.with_updates(nameplate=invalid_nameplate)
    )
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        repo = DppRepoClient(
            "http://repo.test",
            Dpp4FunJsonCodec(),
            validate_dpp4fun,
            client=http,
        )
        _expect(DppValidationClientError, lambda: repo.create_dpp(invalid))
    if requests != 0:
        raise AssertionError(f"validation failure sent {requests} request(s)")
    return "invalid supplier role became DppValidationClientError with zero requests"


def _path_timestamp_and_body_contracts() -> None:
    fixture = build_complete_fixture(_identity())
    encoded = b"*%7E%20%2F%2B%25Gr%C3%BC%C3%9Fe"
    value = "*~ /+%Grüße"
    observed_paths: list[bytes] = []
    observed_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.raw_path)
        observed_bodies.append(request.content)
        if "dppsByIdAndDate" in request.url.path:
            payload: Any = json.loads(to_json(fixture))
        else:
            payload = "accepted"
        return httpx.Response(200, json={"statusCode": "Success", "payload": payload})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        repo = DppRepoClient(
            "http://repo.test",
            Dpp4FunJsonCodec(),
            validate_dpp4fun,
            client=http,
        )
        repo.read_data_element(value, value)
        repo.read_dpp_version_by_id_and_date(
            "DPP 1",
            datetime(2026, 1, 15, 14, 0, 0, 123000, tzinfo=timezone(timedelta(hours=2))),
        )
        repo.update_data_element("D", "$.characteristics.productName", "scalar")
        repo.update_data_element("D", "$.characteristics.color", None)

    expected_element = b"/v1/dpps/" + encoded + b"/elements/" + encoded
    if observed_paths[0] != expected_element:
        raise AssertionError(f"unexpected encoded path {observed_paths[0]!r}")
    expected_history = (
        b"/v1/dppsByIdAndDate/DPP%201?date=2026-01-15T12%3A00%3A00.123Z&representation=full"
    )
    if observed_paths[1] != expected_history:
        raise AssertionError(f"unexpected timestamp path {observed_paths[1]!r}")
    if observed_bodies[2:] != [b'"scalar"', b"null"]:
        raise AssertionError(f"unexpected fine update bodies {observed_bodies[2:]!r}")


class _NullCodec:
    def to_json(self, _value: object) -> str:
        return "{}"

    def from_json(self, _raw: str) -> object:
        return None  # type: ignore[return-value]


def _error_pipeline_contracts() -> None:
    def repo_for(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> tuple[DppRepoClient[Any], httpx.Client]:
        http = httpx.Client(transport=httpx.MockTransport(handler))
        repo = DppRepoClient(
            "http://repo.test",
            _NullCodec(),
            lambda _value: None,
            client=http,
        )
        return repo, http

    repo, http = repo_for(lambda _request: httpx.Response(503, text="unavailable"))
    try:
        error = _expect(DppHttpClientError, lambda: repo.read_dpp_by_id("D"))
        assert isinstance(error, DppHttpClientError) and error.status_code == 503
    finally:
        http.close()

    repo, http = repo_for(
        lambda _request: httpx.Response(
            200,
            json={"statusCode": "ClientErrorBadRequest", "payload": {}},
        )
    )
    try:
        _expect(DppApiClientError, lambda: repo.read_dpp_by_id("D"))
    finally:
        http.close()

    mapping_handlers = (
        lambda _request: httpx.Response(200, text="not-json"),
        lambda _request: httpx.Response(200, json={"payload": {}}),
        lambda _request: httpx.Response(200, json={"statusCode": "Success"}),
        lambda _request: httpx.Response(200, json={"statusCode": "Success", "payload": {}}),
    )
    for index, handler in enumerate(mapping_handlers):
        repo, http = repo_for(handler)
        try:
            error = _expect(
                DppMappingClientError,
                lambda current_repo=repo: current_repo.read_dpp_by_id("D"),
            )
            if error.__cause__ is None:
                raise AssertionError(f"mapping case {index} has no cause")
        finally:
            http.close()

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("controlled network failure", request=request)

    repo, http = repo_for(network_handler)
    try:
        _expect(
            DppNetworkClientError,
            lambda: repo.read_dpp_by_id("D"),
            cause_type=httpx.ConnectError,
        )
    finally:
        http.close()

    sent = 0

    def registry_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(registry_handler)) as registry_http:
        registry = DppRegistryClient("http://registry.test", client=registry_http)
        _expect(
            DppMappingClientError,
            lambda: registry.post_new_dpp_to_registry(None),  # type: ignore[arg-type]
            cause_type=ValueError,
        )
    if sent:
        raise AssertionError("invalid registry request reached transport")


def _rep_17() -> str:
    _path_timestamp_and_body_contracts()
    _error_pipeline_contracts()
    return (
        "exact path/timestamp/body wire; HTTP/API/mapping/network categories; "
        "null payload/codec and invalid registry request causes"
    )


def _rep_18() -> str:
    fixture = build_complete_fixture(_identity())
    observed: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.raw_path)
        return httpx.Response(
            200,
            json={"statusCode": "Success", "payload": json.loads(to_json(fixture))},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        repo = DppRepoClient(
            "http://repo.test",
            Dpp4FunJsonCodec(),
            validate_dpp4fun,
            client=http,
        )
        repo.read_dpp_version_by_product_id_and_date(
            "Product 1",
            datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )
    expected = b"/dppsByProductIdAndDate/Product%201?date=2026-01-15T12%3A00%3A00Z"
    if observed != [expected]:
        raise AssertionError(f"unexpected legacy route {observed!r}")
    return "legacy product-history route shape verified without a Mock-image call"


def _reg_08() -> str:
    observed_keys: list[set[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_keys.append(set(json.loads(request.content)))
        return httpx.Response(
            200,
            json={
                "statusCode": "SuccessCreated",
                "payload": {"registrationId": "registration-1"},
            },
        )

    request = RegisterDppRequest(
        uniqueProductIdentifier="product-1",
        digitalProductPassportId="dpp-1",
        uniqueEconomicOperatorIdentifier="operator-1",
        dppApiEndpoint="http://repo.test",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        registry = DppRegistryClient("http://registry.test", client=http)
        response = registry.post_new_dpp_to_registry(request)
    expected = {
        "uniqueProductIdentifier",
        "digitalProductPassportId",
        "uniqueEconomicOperatorIdentifier",
        "dppApiEndpoint",
    }
    if observed_keys != [expected]:
        raise AssertionError(f"unexpected registry request keys {observed_keys!r}")
    if response.registrationId != "registration-1":
        raise AssertionError("canonical registrationId was not decoded")
    return "four canonical request keys and registrationId response verified"


def run_controlled_scenarios() -> tuple[ScenarioResult, ...]:
    """Run approved deterministic transport/client assertions without external sockets."""

    return (
        _result("REP-16", "Local create validation before I/O", _rep_16),
        _result("REP-17", "Exact wire and client error pipeline", _rep_17),
        _result("REP-18", "Legacy product-history route classification", _rep_18),
        _result("REG-08", "Canonical registry request and response keys", _reg_08),
    )
