"""Final Java client contract checks using deterministic HTTPX transports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from dpp_sdk.clients import (
    DppApiClientError,
    DppApiResponse,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    DppStatusCode,
    MessageType,
    RegisterDppRequest,
)

SUCCESS = {"statusCode": "Success", "payload": {"id": "d-1"}, "message": []}


def transport_for(status: int = 200, body: Any = SUCCESS, seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        content = body if isinstance(body, (str, bytes)) else __import__("json").dumps(body)
        return httpx.Response(status, content=content, request=request)

    return httpx.MockTransport(handler)


def client_for(
    klass: type[Any],
    body: Any = SUCCESS,
    status: int = 200,
    seen: list[httpx.Request] | None = None,
):
    client = httpx.Client(transport=transport_for(status, body, seen))
    return klass("https://api.example/root/", client=client), client


def test_public_payload_contracts_and_canonical_message_cardinality() -> None:
    response = DppApiResponse.model_validate(
        {"statusCode": "Success", "payload": {}, "message": [{"messageType": "Info", "text": "ok"}]}
    )
    assert response.message is not None
    assert response.message[0].message_type is MessageType.Info
    assert DppStatusCode.SuccessCreated.is_success
    assert not DppStatusCode.ServerInternalError.is_success
    assert DppApiResponse.model_validate({"statusCode": "Success", "messages": []}).message is None
    with pytest.raises(ValueError):
        DppStatusCode("ClientErrorNotAuthorized")
    with pytest.raises(ValueError):
        DppStatusCode("ClientErrorForbidden")


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"messageType": None, "text": "detail"},
        {"messageType": "Info"},
        {"messageType": "Info", "text": None},
    ],
)
def test_api_message_requires_table_13_fields(message: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        DppApiResponse.model_validate({"statusCode": "Success", "message": [message]})


def test_api_message_allows_blank_text_and_optional_response_messages() -> None:
    for envelope in (
        {"statusCode": "Success"},
        {"statusCode": "Success", "message": None},
        {"statusCode": "Success", "message": []},
    ):
        DppApiResponse.model_validate(envelope)
    response = DppApiResponse.model_validate(
        {"statusCode": "Success", "message": [{"messageType": "Info", "text": ""}]}
    )
    assert response.message is not None and response.message[0].text == ""


def test_api_response_rejects_null_message_item() -> None:
    with pytest.raises(ValueError):
        DppApiResponse.model_validate({"statusCode": "Success", "message": [None]})


def test_payload_python_names_are_snake_case_and_wire_aliases_remain_canonical() -> None:
    request = RegisterDppRequest(
        unique_product_identifier="p1",
        digital_product_passport_id="d1",
        unique_economic_operator_identifier="o1",
        dpp_api_endpoint="https://repo.example",
    )

    assert request.model_dump(mode="json", by_alias=True, exclude_none=False) == {
        "uniqueProductIdentifier": "p1",
        "digitalProductPassportId": "d1",
        "uniqueEconomicOperatorIdentifier": "o1",
        "dppApiEndpoint": "https://repo.example",
    }
    assert not hasattr(request, "uniqueProductIdentifier")


@pytest.mark.parametrize("client_type", [DppRepoClient, DppRegistryClient])
def test_client_rejects_malformed_base_uri(client_type) -> None:
    for base_url in (
        "https://example.com/%zz",
        "example.com/api",
        "ftp://example.com/api",
        "https:///missing-host",
        "https://example.com:bad",
        "https://example.com:99999",
        "https://example.com?tenant=one",
        "https://example.com#fragment",
        "https://example.com?",
        "https://example.com#",
    ):
        with pytest.raises(ValueError):
            client_type(base_url)


@pytest.mark.parametrize("client_type", [DppRepoClient, DppRegistryClient])
def test_client_accepts_absolute_http_localhost_base_uri(client_type) -> None:
    client = client_type("http://localhost:8080/api")
    client.close()


def test_create_response_ignores_legacy_identifier_alias() -> None:
    client, caller_client = client_for(
        DppRepoClient, {"statusCode": "Success", "payload": {"dppId": "old"}}
    )
    try:
        result = client.create_dpp({"digitalProductPassportId": "canonical"})
        assert result.digital_product_passport_id is None
    finally:
        caller_client.close()


@pytest.mark.parametrize(
    ("operation", "method", "url", "body", "representation"),
    [
        ("create", "POST", "https://api.example/root/v1/dpps", {"id": "d-1"}, None),
        (
            "create_full",
            "POST",
            "https://api.example/root/v1/dpps?representation=full",
            {"id": "d-1"},
            None,
        ),
        (
            "read_id",
            "GET",
            "https://api.example/root/v1/dpps/d%2F1?representation=full",
            None,
            "FULL",
        ),
        ("read_product", "GET", "https://api.example/root/v1/dppsByProductId/p%2F1", None, None),
        (
            "history",
            "GET",
            "https://api.example/root/v1/dppsByIdAndDate/d%2F1?date=2026-05-11T09%3A30%3A15Z&representation=full",
            None,
            "FULL",
        ),
        (
            "ids",
            "POST",
            "https://api.example/root/v1/dppsByProductIds",
            {"productIdentifiers": ["p1"], "limit": 5, "cursor": "c"},
            None,
        ),
        (
            "update",
            "PATCH",
            "https://api.example/root/v1/dpps/d%2F1?representation=full",
            {"name": "n"},
            "FULL",
        ),
        ("delete", "DELETE", "https://api.example/root/v1/dpps/d%2F1", None, None),
        (
            "element_read",
            "GET",
            "https://api.example/root/v1/dpps/d%2F1/elements/%24%5B%27name%27%5D?representation=full",
            None,
            "FULL",
        ),
        (
            "element_update",
            "PATCH",
            "https://api.example/root/v1/dpps/d%2F1/elements/%24%5B%27name%27%5D",
            "value",
            None,
        ),
    ],
)
def test_repository_operation_contracts(
    operation: str, method: str, url: str, body: Any, representation: str | None
) -> None:
    seen: list[httpx.Request] = []
    payload = (
        {"dppIdentifiers": ["d-1"]}
        if operation == "ids"
        else {"digitalProductPassportId": "d-1"}
        if operation.startswith("create")
        else {"id": "d-1"}
    )
    client, raw = client_for(
        DppRepoClient, {"statusCode": "Success", "payload": payload, "message": []}, seen=seen
    )
    rep = DppRepresentation[representation] if representation else DppRepresentation.COMPRESSED
    date = datetime(2026, 5, 11, 9, 30, 15, tzinfo=UTC)
    calls = {
        "create": lambda: client.create_dpp(body, rep),
        "create_full": lambda: client.create_dpp(body, DppRepresentation.FULL),
        "read_id": lambda: client.read_dpp_by_id("d/1", rep),
        "read_product": lambda: client.read_dpp_by_product_id("p/1"),
        "history": lambda: client.read_dpp_version_by_id_and_date("d/1", date, rep),
        "ids": lambda: client.read_dpp_ids_by_product_ids(["p1"], 5, "c"),
        "update": lambda: client.update_dpp_by_id("d/1", body, rep),
        "delete": lambda: client.delete_dpp_by_id("d/1"),
        "element_read": lambda: client.read_data_element("d/1", "$['name']", rep),
        "element_update": lambda: client.update_data_element("d/1", "$['name']", body),
    }
    result = calls[operation]()
    request = seen[0]
    assert request.method == method
    assert str(request.url) == url
    if body is not None:
        assert request.headers["content-type"] == "application/json"
        assert request.read() == __import__("json").dumps(body, separators=(",", ":")).encode()
    assert result is not None
    raw.close()


def test_registry_operation_uses_canonical_request_and_response_fields() -> None:
    seen: list[httpx.Request] = []
    registry, raw = client_for(
        DppRegistryClient,
        {"statusCode": "SuccessCreated", "payload": {"registrationId": "r1"}, "message": []},
        seen=seen,
    )
    result = registry.post_new_dpp_to_registry(
        RegisterDppRequest(
            unique_product_identifier="p1",
            digital_product_passport_id="d1",
            unique_economic_operator_identifier="o1",
            dpp_api_endpoint="https://repo.example",
        )
    )
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.example/root/v1/registerDPP"
    assert __import__("json").loads(request.read()) == {
        "uniqueProductIdentifier": "p1",
        "digitalProductPassportId": "d1",
        "uniqueEconomicOperatorIdentifier": "o1",
        "dppApiEndpoint": "https://repo.example",
    }
    assert result.registration_id == "r1"
    raw.close()


def test_204_and_operation_specific_payloads_keep_envelope_metadata() -> None:
    message = [{"messageType": "Warning", "text": "accepted without body", "code": "C1"}]
    repo, raw = client_for(
        DppRepoClient,
        {
            "statusCode": "SuccessCreated",
            "payload": {"digitalProductPassportId": "d1"},
            "message": message,
        },
        status=201,
    )
    created = repo.create_dpp({"anything": True})
    assert created.digital_product_passport_id == "d1"
    assert created.status_code is DppStatusCode.SuccessCreated
    assert created.message is not None and created.message[0].code == "C1"
    raw.close()

    repo, raw = client_for(DppRepoClient, "", status=204)
    deleted = repo.delete_dpp_by_id("d1")
    assert deleted.status_code is DppStatusCode.SuccessNoContent
    assert deleted.message is None
    raw.close()


@pytest.mark.parametrize(
    "body",
    [
        {"statusCode": "Success", "payload": "not-an-object", "message": []},
        {"statusCode": "Success", "payload": {}, "message": []},
    ],
)
def test_registry_mapping_failures_are_distinct_from_api_failures(body: Any) -> None:
    registry, raw = client_for(DppRegistryClient, body)
    if body["payload"] == {}:
        # An absent registration ID is allowed by the Java response payload.
        assert (
            registry.post_new_dpp_to_registry({"uniqueProductIdentifier": "p1"}).registration_id
            is None
        )
    else:
        with pytest.raises(DppMappingClientError):
            registry.post_new_dpp_to_registry({"uniqueProductIdentifier": "p1"})
    raw.close()


def test_registry_response_uses_only_the_canonical_registration_id() -> None:
    registry, raw = client_for(
        DppRegistryClient,
        {"statusCode": "Success", "payload": {"registryIdentifier": "legacy"}, "message": []},
    )
    response = registry.post_new_dpp_to_registry({"uniqueProductIdentifier": "p1"})
    assert response.registration_id is None


def test_registry_204_empty_body_is_a_mapping_failure() -> None:
    registry, raw = client_for(DppRegistryClient, "", status=204)
    with pytest.raises(DppMappingClientError):
        registry.post_new_dpp_to_registry({"uniqueProductIdentifier": "p1"})
    raw.close()
    raw.close()


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (503, "offline", DppHttpClientError),
        (503, {"statusCode": "ServerErrorBadGateway", "message": []}, DppApiClientError),
        (200, "{", DppMappingClientError),
        (200, {"payload": {}}, DppMappingClientError),
        (
            200,
            {
                "statusCode": "Success",
                "payload": {},
                "message": [{"messageType": "Info", "timestamp": "2026-01-01T12:00:00"}],
            },
            DppMappingClientError,
        ),
        (
            200,
            {
                "statusCode": "ClientErrorResourceNotFound",
                "message": [{"messageType": "Error", "text": "gone"}],
            },
            DppApiClientError,
        ),
        (
            200,
            {"statusCode": "Success", "message": [{"messageType": "Info"}]},
            DppMappingClientError,
        ),
        (
            503,
            {"statusCode": "ServerErrorBadGateway", "message": [{"text": "broken"}]},
            DppHttpClientError,
        ),
    ],
)
def test_response_error_families(status: int, body: Any, error: type[Exception]) -> None:
    repo, raw = client_for(DppRepoClient, body, status)
    with pytest.raises(error):
        repo.read_dpp_by_id("d1")
    raw.close()


def test_network_and_timeout_errors_are_distinct() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    repo = DppRepoClient(
        "https://api.example", client=httpx.Client(transport=httpx.MockTransport(fail))
    )
    with pytest.raises(DppNetworkClientError):
        repo.read_dpp_by_id("d1")

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    repo = DppRepoClient(
        "https://api.example", client=httpx.Client(transport=httpx.MockTransport(timeout))
    )
    with pytest.raises(DppNetworkClientError, match="timed out"):
        repo.read_dpp_by_id("d1")


def test_required_payload_and_context_ownership() -> None:
    repo, raw = client_for(DppRepoClient, {"statusCode": "Success", "payload": None, "message": []})
    with pytest.raises(DppMappingClientError, match="payload"):
        repo.read_data_element("d1", "$.name")
    repo.close()
    assert not raw.is_closed
    raw.close()


def test_request_mapping_failure_happens_before_transport() -> None:
    seen: list[httpx.Request] = []
    repo, raw = client_for(DppRepoClient, seen=seen)
    with pytest.raises(DppMappingClientError):
        repo.create_dpp({"unserializable": object()})
    with pytest.raises(TypeError):
        repo.create_dpp(None)
    assert seen == []
    raw.close()
