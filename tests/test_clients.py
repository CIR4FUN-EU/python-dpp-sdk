"""HTTP client behavior against a mocked httpx transport."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from dpp_sdk.clients import (
    DppApiClientError,
    DppClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppRegistryClient,
    DppRepoClient,
    DppValidationClientError,
    RegisterDppRequest,
    UpdateDataElementRequest,
)
from dpp_sdk.clients.payloads import (
    CreateDppResponse,
    DeleteDppResponse,
    DppApiMessage,
    DppApiResponse,
    DppStatusCode,
    MessageType,
    ReadDppIdsRequest,
    ReadDppIdsResponse,
    RegisterDppResponse,
)
from dpp_sdk.core.errors import DppMappingError
from dpp_sdk.dpp4fun.model import Dpp4Fun
from dpp_sdk.dpp4fun.transport import Dpp4FunJsonCodec, to_json
from dpp_sdk.dpp4fun.validation import validate_dpp4fun


def _make_repo(handler, **kwargs) -> DppRepoClient[Dpp4Fun]:  # type: ignore[no-untyped-def]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return DppRepoClient(
        "http://repo.test/",
        codec=Dpp4FunJsonCodec(),
        validator=validate_dpp4fun,
        client=client,
        **kwargs,
    )


def test_create_returns_dpp_id(valid_dpp4fun: Dpp4Fun) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201, json={"statusCode": "SuccessCreated", "payload": {"dppId": "DPP-1"}}
        )

    repo = _make_repo(handler)
    result = repo.create_dpp(valid_dpp4fun)
    assert result.dppId == "DPP-1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/dpps"
    # the create body is the flat transport shape
    assert "passportMetadata" in captured["body"]  # type: ignore[operator]


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DPP-BY-ID-001"])
def test_read_by_id_decodes_via_codec(contract_id: str, valid_dpp4fun: Dpp4Fun) -> None:
    flat = json.loads(to_json(valid_dpp4fun))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/v1/dpps/DPP-1?representation=full"
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    assert _make_repo(handler).read_dpp_by_id("DPP-1") == valid_dpp4fun


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DPP-BY-PRODUCT-ID-001"])
def test_read_by_product_id_encodes_path(contract_id: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/dppsByProductId/GTIN 0001"
        assert request.url.raw_path == b"/v1/dppsByProductId/GTIN%200001?representation=full"
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"x": 1}})

    # codec.from_json will fail on this dummy payload; we only assert the URL.
    with pytest.raises(Exception):  # noqa: B017, PT011
        _make_repo(handler).read_dpp_by_product_id("GTIN 0001")


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DPP-IDS-BY-PRODUCT-IDS-001"])
def test_read_dpp_ids(contract_id: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/v1/dppsByProductIds"
        return httpx.Response(
            200,
            json={
                "statusCode": "Success",
                "payload": {"dppIdentifiers": ["a", "b"], "nextCursor": "c2"},
            },
        )

    result = _make_repo(handler).read_dpp_ids_by_product_ids(["p1"], limit=10)
    assert result.dppIdentifiers == ["a", "b"]
    assert result.nextCursor == "c2"


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-UPDATE-DATA-ELEMENT-001"])
def test_update_data_element_sends_direct_payload(contract_id: str) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"statusCode": "Success", "payload": 42})

    result = _make_repo(handler).update_data_element("DPP-1", "$.weight", 42)
    assert result == 42
    assert seen["path"] == "/v1/dpps/DPP-1/elements/$.weight"
    assert seen["body"] == 42


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DATA-ELEMENT-001"])
def test_read_data_element_returns_the_raw_selected_json_value(contract_id: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.raw_path == b"/v1/dpps/DPP%201/elements/%24.characteristics.weight"
        return httpx.Response(200, json={"statusCode": "Success", "payload": 42})

    assert _make_repo(handler).read_data_element("DPP 1", "$.characteristics.weight") == 42


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param("read", id="element-read"),
        pytest.param("update", id="element-update"),
    ],
)
def test_element_null_payload_is_a_causal_mapping_error(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"statusCode": "Success", "payload": None})

    repo = _make_repo(handler)
    with pytest.raises(DppMappingClientError, match="payload") as exc:
        if operation == "read":
            repo.read_data_element("DPP-1", "$.weight")
        else:
            repo.update_data_element("DPP-1", "$.weight", 42)
    assert isinstance(exc.value.__cause__, ValueError)
    assert "payload" in str(exc.value.__cause__)


def test_compatibility_element_dto_cannot_change_canonical_direct_body() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    compatibility_dto = UpdateDataElementRequest(payload={"weight": 42})
    _make_repo(handler).update_data_element("DPP-1", "$.weight", compatibility_dto.payload)
    assert seen["body"] == {"weight": 42}


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-DELETE-DPP-BY-ID-001"])
def test_delete_returns_status(contract_id: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.raw_path == b"/v1/dpps/DPP-1"
        return httpx.Response(200, json={"statusCode": "SuccessNoContent", "messages": []})

    assert _make_repo(handler).delete_dpp_by_id("DPP-1").statusCode is not None


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-COMPRESSED-DPP-BY-ID-001"])
def test_read_compressed_dpp_returns_raw_payload_without_codec(contract_id: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/v1/dpps/DPP%201?representation=compressed"
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"compressed": True}})

    assert _make_repo(handler).read_compressed_dpp_by_id("DPP 1") == {"compressed": True}


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DPP-VERSION-BY-ID-AND-DATE-001"])
def test_dpp_id_history_uses_versioned_path_and_ordered_query(
    contract_id: str, valid_dpp4fun: Dpp4Fun
) -> None:
    flat = json.loads(to_json(valid_dpp4fun))

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.raw_path == b"/v1/dppsByIdAndDate/DPP%201?date=2026-01-15T12%3A00%3A00Z"
            b"&representation=full"
        )
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    assert (
        _make_repo(handler).read_dpp_version_by_id_and_date(
            "DPP 1", datetime(2026, 1, 15, 12, tzinfo=UTC)
        )
        == valid_dpp4fun
    )


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-READ-DPP-VERSION-BY-PRODUCT-ID-AND-DATE-001"])
def test_product_id_history_is_retained_unversioned_compatibility(
    contract_id: str, valid_dpp4fun: Dpp4Fun
) -> None:
    flat = json.loads(to_json(valid_dpp4fun))

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.raw_path
            == b"/dppsByProductIdAndDate/GTIN%201?date=2026-01-15T12%3A00%3A00Z"
        )
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    assert (
        _make_repo(handler).read_dpp_version_by_product_id_and_date(
            "GTIN 1", datetime(2026, 1, 15, 12, tzinfo=UTC)
        )
        == valid_dpp4fun
    )


@pytest.mark.parametrize(
    ("date", "expected_query"),
    [
        pytest.param(
            datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
            b"2024-01-02T03%3A04%3A05Z",
            id="utc-aware",
        ),
        pytest.param(
            datetime(2024, 1, 2, 4, 4, 5, tzinfo=timezone(timedelta(hours=1))),
            b"2024-01-02T03%3A04%3A05Z",
            id="positive-offset",
        ),
        pytest.param(
            datetime(2024, 1, 1, 22, 4, 5, tzinfo=timezone(timedelta(hours=-5))),
            b"2024-01-02T03%3A04%3A05Z",
            id="negative-offset-crosses-forward-date-boundary",
        ),
        pytest.param(
            datetime(2024, 1, 2, 0, 30, tzinfo=timezone(timedelta(hours=1))),
            b"2024-01-01T23%3A30%3A00Z",
            id="positive-offset-crosses-backward-date-boundary",
        ),
        pytest.param(
            datetime(2024, 1, 2, 3, 4, 5, 123000, tzinfo=UTC),
            b"2024-01-02T03%3A04%3A05.123Z",
            id="millisecond-fraction",
        ),
        pytest.param(
            datetime(2024, 1, 2, 3, 4, 5, 123456, tzinfo=UTC),
            b"2024-01-02T03%3A04%3A05.123456Z",
            id="microsecond-fraction",
        ),
    ],
)
@pytest.mark.parametrize(
    ("route_family", "expected_prefix", "expected_suffix"),
    [
        pytest.param(
            "dpp-id",
            b"/v1/dppsByIdAndDate/DPP%201?date=",
            b"&representation=full",
            id="dpp-id-history",
        ),
        pytest.param(
            "product-id",
            b"/dppsByProductIdAndDate/DPP%201?date=",
            b"",
            id="product-id-history",
        ),
    ],
)
def test_history_timestamp_wire_is_canonical_utc_z(
    route_family: str,
    expected_prefix: bytes,
    expected_suffix: bytes,
    date: datetime,
    expected_query: bytes,
    valid_dpp4fun: Dpp4Fun,
) -> None:
    flat = json.loads(to_json(valid_dpp4fun))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == expected_prefix + expected_query + expected_suffix
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    repo = _make_repo(handler)
    if route_family == "dpp-id":
        result = repo.read_dpp_version_by_id_and_date("DPP 1", date)
    else:
        result = repo.read_dpp_version_by_product_id_and_date("DPP 1", date)
    assert result == valid_dpp4fun


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        pytest.param("*", b"%2A", id="star"),
        pytest.param("~", b"%7E", id="tilde"),
        pytest.param("a b", b"a%20b", id="space"),
        pytest.param("/", b"%2F", id="slash"),
        pytest.param("+", b"%2B", id="plus"),
        pytest.param("%", b"%25", id="percent"),
        pytest.param("?", b"%3F", id="question-mark"),
        pytest.param("#", b"%23", id="hash"),
        pytest.param("a~b%?#", b"a%7Eb%25%3F%23", id="refreshed-parent-combined-vector"),
        pytest.param("Grüße", b"Gr%C3%BC%C3%9Fe", id="unicode-non-ascii"),
        pytest.param("a%2Fb", b"a%252Fb", id="already-percent-looking"),
    ],
)
@pytest.mark.parametrize(
    "route_family",
    [
        pytest.param("delete-dpp-by-id", id="delete-dpp-by-id"),
        pytest.param("read-compressed-dpp-by-id", id="read-compressed-dpp-by-id"),
        pytest.param("read-data-element", id="read-data-element"),
        pytest.param("read-dpp-by-id", id="read-dpp-by-id"),
        pytest.param("read-dpp-by-product-id", id="read-dpp-by-product-id"),
        pytest.param("read-dpp-version-by-id-and-date", id="read-dpp-version-by-id-and-date"),
        pytest.param(
            "read-dpp-version-by-product-id-and-date",
            id="read-dpp-version-by-product-id-and-date",
        ),
        pytest.param("update-data-element", id="update-data-element"),
        pytest.param("update-dpp-by-id", id="update-dpp-by-id"),
    ],
)
def test_dynamic_path_segment_wire_is_exact_for_every_route_family(
    route_family: str,
    value: str,
    encoded: bytes,
    valid_dpp4fun: Dpp4Fun,
) -> None:
    flat = json.loads(to_json(valid_dpp4fun))
    if route_family == "read-dpp-by-product-id":
        expected_path = b"/v1/dppsByProductId/" + encoded + b"?representation=full"
    elif route_family == "read-dpp-version-by-id-and-date":
        expected_path = (
            b"/v1/dppsByIdAndDate/"
            + encoded
            + b"?date=2024-01-02T03%3A04%3A05Z&representation=full"
        )
    elif route_family == "read-dpp-version-by-product-id-and-date":
        expected_path = b"/dppsByProductIdAndDate/" + encoded + b"?date=2024-01-02T03%3A04%3A05Z"
    elif route_family in {"read-data-element", "update-data-element"}:
        expected_path = b"/v1/dpps/" + encoded + b"/elements/" + encoded
    elif route_family == "read-dpp-by-id":
        expected_path = b"/v1/dpps/" + encoded + b"?representation=full"
    elif route_family == "read-compressed-dpp-by-id":
        expected_path = b"/v1/dpps/" + encoded + b"?representation=compressed"
    else:
        expected_path = b"/v1/dpps/" + encoded

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == expected_path
        status = "SuccessNoContent" if route_family == "delete-dpp-by-id" else "Success"
        payload: Any = 42 if route_family in {"read-data-element", "update-data-element"} else flat
        return httpx.Response(200, json={"statusCode": status, "payload": payload})

    repo = _make_repo(handler)
    if route_family == "delete-dpp-by-id":
        repo.delete_dpp_by_id(value)
    elif route_family == "read-compressed-dpp-by-id":
        repo.read_compressed_dpp_by_id(value)
    elif route_family == "read-data-element":
        repo.read_data_element(value, value)
    elif route_family == "read-dpp-by-id":
        repo.read_dpp_by_id(value)
    elif route_family == "read-dpp-by-product-id":
        repo.read_dpp_by_product_id(value)
    elif route_family == "read-dpp-version-by-id-and-date":
        repo.read_dpp_version_by_id_and_date(value, datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC))
    elif route_family == "read-dpp-version-by-product-id-and-date":
        repo.read_dpp_version_by_product_id_and_date(
            value, datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        )
    elif route_family == "update-data-element":
        repo.update_data_element(value, value, {"updated": True})
    else:
        repo.update_dpp_by_id(value, {"updated": True})


@pytest.mark.parametrize("contract_id", ["CLIENT-REPO-UPDATE-DPP-BY-ID-001"])
def test_partial_patch_decodes_response_without_whole_model_validation(
    contract_id: str,
    valid_dpp4fun: Dpp4Fun,
) -> None:
    flat = json.loads(to_json(valid_dpp4fun))
    validator_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/v1/dpps/DPP%201"
        assert json.loads(request.content) == {"characteristics": {"productName": "updated"}}
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    def validator(dpp: Dpp4Fun) -> None:
        nonlocal validator_calls
        validator_calls += 1

    repo = DppRepoClient(
        "http://repo.test",
        codec=Dpp4FunJsonCodec(),
        validator=validator,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert (
        repo.update_dpp_by_id("DPP 1", {"characteristics": {"productName": "updated"}})
        == valid_dpp4fun
    )
    assert validator_calls == 0


@pytest.mark.parametrize("payload", [None, "text", 1, True, ["a"], {"x": 1}])
def test_element_patch_preserves_every_json_value_and_bypasses_validator(payload: Any) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/v1/dpps/DPP%201/elements/%24%5B%27a%2Fb%27%5D"
        assert json.loads(request.content) == payload
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    def validator(dpp: Dpp4Fun) -> None:
        nonlocal calls
        calls += 1

    repo = DppRepoClient(
        "http://repo.test",
        codec=Dpp4FunJsonCodec(),
        validator=validator,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert repo.update_data_element("DPP 1", "$['a/b']", payload) == {"accepted": True}
    assert calls == 0


def test_repository_identifier_and_element_preconditions_fail_before_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("local precondition must prevent network I/O")

    repo = _make_repo(handler)
    with pytest.raises(ValueError):
        repo.read_dpp_by_id(" ")
    with pytest.raises(ValueError):
        repo.update_data_element("D", " ", None)
    with pytest.raises(ValueError):
        repo.read_dpp_version_by_id_and_date("D", datetime(2026, 1, 15))


def test_api_error_status_raises_with_messages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "statusCode": "ClientErrorResourceNotFound",
                "messages": [{"messageType": "Error", "text": "not found"}],
            },
        )

    with pytest.raises(DppApiClientError) as exc:
        _make_repo(handler).read_dpp_by_id("missing")
    assert exc.value.messages is not None
    assert exc.value.messages[0].text == "not found"


def test_http_error_status_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(DppHttpClientError) as exc:
        _make_repo(handler).read_dpp_by_id("x")
    assert exc.value.status_code == 500


def test_status_code_alias_is_accepted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # The Java @JsonCreator alias must map to ClientForbidden.
        return httpx.Response(200, json={"statusCode": "ClientErrorForbidden", "messages": []})

    with pytest.raises(DppApiClientError) as exc:
        _make_repo(handler).read_dpp_by_id("x")
    assert exc.value.status_code is not None
    assert exc.value.status_code.value == "ClientForbidden"


def test_shared_payloads_emit_canonical_status_and_timestamp() -> None:
    response = DppApiResponse.model_validate(
        {
            "statusCode": "ServerNotImplemented",
            "messages": [
                {
                    "messageType": "Warning",
                    "correlationId": "c-1",
                    "timestamp": "2026-01-15T12:00:00+00:00",
                }
            ],
            "unknown": "ignored",
        }
    )
    assert response.statusCode is DppStatusCode.ServerNotImplemented
    assert response.model_dump(mode="json")["statusCode"] == "ServerNotImplemented"
    assert response.messages == [
        DppApiMessage(
            messageType=MessageType.Warning,
            correlationId="c-1",
            timestamp=response.messages[0].timestamp if response.messages else None,
        )
    ]


@pytest.mark.parametrize(
    "response_payload",
    [
        pytest.param({"registrationId": "REG-1"}, id="canonical-response"),
        pytest.param({"registryIdentifier": "REG-1"}, id="legacy-response-input"),
    ],
)
def test_registry_register_uses_canonical_wire_contract(
    response_payload: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.raw_path == b"/v1/registerDPP"
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == {
            "uniqueProductIdentifier": "GTIN-0001",
            "digitalProductPassportId": "DPP-1",
            "uniqueEconomicOperatorIdentifier": None,
            "dppApiEndpoint": None,
        }
        return httpx.Response(
            201,
            json={"statusCode": "SuccessCreated", "payload": response_payload},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    registry = DppRegistryClient("http://reg.test", client=client)
    response = registry.post_new_dpp_to_registry(
        RegisterDppRequest.model_validate(
            {"productIdentifier": "GTIN-0001", "dppIdentifier": "DPP-1"}
        )
    )
    assert response.registrationId == "REG-1"
    assert response.model_dump() == {"registrationId": "REG-1"}


@pytest.mark.parametrize(
    "registry_request",
    [
        pytest.param(None, id="null-request"),
        pytest.param(
            RegisterDppRequest.model_construct(uniqueProductIdentifier=object()),
            id="structurally-invalid-request",
        ),
    ],
)
def test_registry_invalid_request_is_a_causal_mapping_error_before_network(
    registry_request: RegisterDppRequest | None,
) -> None:
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"statusCode": "Success", "payload": {"registrationId": "R"}}
        )

    registry = DppRegistryClient(
        "http://reg.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(DppMappingClientError, match="request") as exc:
        registry.post_new_dpp_to_registry(registry_request)  # type: ignore[arg-type]
    assert exc.value.__cause__ is not None
    assert str(exc.value.__cause__)
    assert not isinstance(exc.value.__cause__, AttributeError)
    assert calls == 0


@pytest.mark.parametrize(
    ("contract_id", "response", "expected_error"),
    [
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-http",
            httpx.Response(500, text="boom"),
            DppHttpClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-http",
        ),
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-malformed-envelope",
            httpx.Response(200, text="not-json"),
            DppMappingClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-malformed-envelope",
        ),
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-api-error",
            httpx.Response(200, json={"statusCode": "ClientErrorBadRequest", "messages": []}),
            DppApiClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-api-error",
        ),
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-missing-payload",
            httpx.Response(200, json={"statusCode": "Success"}),
            DppMappingClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-missing-payload",
        ),
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-blank-registration-id",
            httpx.Response(200, json={"statusCode": "Success", "payload": {"registrationId": " "}}),
            DppMappingClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-blank-registration-id",
        ),
        pytest.param(
            "CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-unmappable-registration-id",
            httpx.Response(200, json={"statusCode": "Success", "payload": {"registrationId": []}}),
            DppMappingClientError,
            id="CLIENT-REGISTRY-POST-NEW-DPP-TO-REGISTRY-001-unmappable-registration-id",
        ),
    ],
)
def test_registry_register_preserves_shared_error_categories(
    contract_id: str, response: httpx.Response, expected_error: type[Exception]
) -> None:
    registry = DppRegistryClient(
        "http://reg.test",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: response)),
    )
    with pytest.raises(expected_error):
        registry.post_new_dpp_to_registry(RegisterDppRequest())


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(httpx.ReadTimeout("timeout"), id="timeout"),
        pytest.param(httpx.ConnectError("transport"), id="transport"),
    ],
)
def test_registry_register_translates_network_errors_with_cause(error: Exception) -> None:
    registry = DppRegistryClient(
        "http://reg.test",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(error))
        ),
    )
    with pytest.raises(DppNetworkClientError) as exc:
        registry.post_new_dpp_to_registry(RegisterDppRequest())
    assert exc.value.__cause__ is error


def test_registry_payload_canonical_keys_and_legacy_input_aliases() -> None:
    request = RegisterDppRequest.model_validate(
        {"productIdentifier": "P", "dppIdentifier": "D", "operatorIdentifier": "O", "repoUrl": "U"}
    )
    assert request.model_dump() == {
        "uniqueProductIdentifier": "P",
        "digitalProductPassportId": "D",
        "uniqueEconomicOperatorIdentifier": "O",
        "dppApiEndpoint": "U",
    }
    assert RegisterDppResponse.model_validate({"registryIdentifier": "R"}).model_dump() == {
        "registrationId": "R"
    }


@pytest.mark.parametrize(
    ("contract_id", "status"),
    [
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-ERROR-BAD-REQUEST",
            DppStatusCode.ClientErrorBadRequest,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-ERROR-BAD-REQUEST",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-METHOD-NOT-ALLOWED",
            DppStatusCode.ClientMethodNotAllowed,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-METHOD-NOT-ALLOWED",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-NOT-AUTHORIZED",
            DppStatusCode.ClientNotAuthorized,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-NOT-AUTHORIZED",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-RESOURCE-CONFLICT",
            DppStatusCode.ClientResourceConflict,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-CLIENT-RESOURCE-CONFLICT",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-ERROR-BAD-GATEWAY",
            DppStatusCode.ServerErrorBadGateway,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-ERROR-BAD-GATEWAY",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-INTERNAL-ERROR",
            DppStatusCode.ServerInternalError,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-INTERNAL-ERROR",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-NOT-IMPLEMENTED",
            DppStatusCode.ServerNotImplemented,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SERVER-NOT-IMPLEMENTED",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SUCCESS-ACCEPTED",
            DppStatusCode.SuccessAccepted,
            id="PAYLOAD-SHARED-DPP-STATUS-CODE-FIELD-SUCCESS-ACCEPTED",
        ),
    ],
)
def test_status_values_round_trip_with_exact_wire_value(
    contract_id: str, status: DppStatusCode
) -> None:
    assert DppStatusCode(status.value) is status
    assert DppApiResponse(statusCode=status).model_dump(mode="json")["statusCode"] == status.value


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param("PAYLOAD-SHARED-DPP-STATUS-CODE", id="PAYLOAD-SHARED-DPP-STATUS-CODE"),
        pytest.param("PAYLOAD-SHARED-DPP-API-RESPONSE", id="PAYLOAD-SHARED-DPP-API-RESPONSE"),
        pytest.param("PAYLOAD-SHARED-DPP-API-MESSAGE", id="PAYLOAD-SHARED-DPP-API-MESSAGE"),
        pytest.param(
            "PAYLOAD-SHARED-DPP-API-MESSAGE-FIELD-CORRELATION-ID",
            id="PAYLOAD-SHARED-DPP-API-MESSAGE-FIELD-CORRELATION-ID",
        ),
        pytest.param(
            "PAYLOAD-SHARED-DPP-API-MESSAGE-FIELD-TIMESTAMP",
            id="PAYLOAD-SHARED-DPP-API-MESSAGE-FIELD-TIMESTAMP",
        ),
        pytest.param("PAYLOAD-SHARED-MESSAGE-TYPE", id="PAYLOAD-SHARED-MESSAGE-TYPE"),
        pytest.param(
            "PAYLOAD-SHARED-MESSAGE-TYPE-FIELD-WARNING",
            id="PAYLOAD-SHARED-MESSAGE-TYPE-FIELD-WARNING",
        ),
    ],
)
def test_shared_payload_defaults_timestamp_and_unknown_fields(contract_id: str) -> None:
    timestamp = datetime(2026, 1, 15, 12, tzinfo=UTC)
    response = DppApiResponse.model_validate(
        {
            "statusCode": "SuccessAccepted",
            "payload": None,
            "messages": [
                {
                    "messageType": "Warning",
                    "correlationId": "c-1",
                    "timestamp": timestamp.isoformat(),
                }
            ],
            "unknown": "ignored",
        }
    )
    assert response.payload is None
    assert response.messages is not None
    assert response.messages[0].timestamp == timestamp
    assert response.model_dump(mode="json")["messages"][0]["timestamp"] == "2026-01-15T12:00:00Z"


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param("PAYLOAD-REPO-CREATE-DPP-RESPONSE", id="PAYLOAD-REPO-CREATE-DPP-RESPONSE"),
        pytest.param("PAYLOAD-REPO-DELETE-DPP-RESPONSE", id="PAYLOAD-REPO-DELETE-DPP-RESPONSE"),
        pytest.param("PAYLOAD-REPO-READ-DPP-IDS-REQUEST", id="PAYLOAD-REPO-READ-DPP-IDS-REQUEST"),
        pytest.param(
            "PAYLOAD-REPO-READ-DPP-IDS-REQUEST-FIELD-PRODUCT-IDENTIFIERS",
            id="PAYLOAD-REPO-READ-DPP-IDS-REQUEST-FIELD-PRODUCT-IDENTIFIERS",
        ),
        pytest.param("PAYLOAD-REPO-READ-DPP-IDS-RESPONSE", id="PAYLOAD-REPO-READ-DPP-IDS-RESPONSE"),
    ],
)
def test_repository_dtos_preserve_nulls_defaults_and_unknown_field_policy(contract_id: str) -> None:
    assert CreateDppResponse.model_validate({"dppId": "D", "unknown": 1}).dppId == "D"
    assert DeleteDppResponse().model_dump() == {"statusCode": None, "messages": None}
    assert ReadDppIdsRequest(productIdentifiers=["P"], limit=None, cursor=None).model_dump() == {
        "productIdentifiers": ["P"],
        "limit": None,
        "cursor": None,
    }
    assert ReadDppIdsResponse.model_validate(
        {"dppIdentifiers": ["D"], "unknown": 1}
    ).model_dump() == {
        "dppIdentifiers": ["D"],
        "nextCursor": None,
    }


@pytest.mark.parametrize(
    ("contract_id", "raw"),
    [
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST",
            {
                "uniqueProductIdentifier": "P",
                "digitalProductPassportId": "D",
                "uniqueEconomicOperatorIdentifier": "O",
                "dppApiEndpoint": "U",
            },
            id="PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST",
        ),
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-DIGITAL-PRODUCT-PASSPORT-ID",
            {"dppIdentifier": "D"},
            id="PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-DIGITAL-PRODUCT-PASSPORT-ID",
        ),
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-DPP-API-ENDPOINT",
            {"repoUrl": "U"},
            id="PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-DPP-API-ENDPOINT",
        ),
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-UNIQUE-ECONOMIC-OPERATOR-IDENTIFIER",
            {"operatorIdentifier": "O"},
            id="PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-UNIQUE-ECONOMIC-OPERATOR-IDENTIFIER",
        ),
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-UNIQUE-PRODUCT-IDENTIFIER",
            {"productIdentifier": "P"},
            id="PAYLOAD-REGISTRY-REGISTER-DPP-REQUEST-FIELD-UNIQUE-PRODUCT-IDENTIFIER",
        ),
    ],
)
def test_registry_request_aliases_are_input_only_and_canonical_output(
    contract_id: str, raw: dict[str, str]
) -> None:
    request = RegisterDppRequest.model_validate(raw)
    dumped = request.model_dump()
    assert set(dumped) == {
        "uniqueProductIdentifier",
        "digitalProductPassportId",
        "uniqueEconomicOperatorIdentifier",
        "dppApiEndpoint",
    }
    assert not {"productIdentifier", "dppIdentifier", "operatorIdentifier", "repoUrl"} & set(dumped)


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-RESPONSE", id="PAYLOAD-REGISTRY-REGISTER-DPP-RESPONSE"
        ),
        pytest.param(
            "PAYLOAD-REGISTRY-REGISTER-DPP-RESPONSE-FIELD-REGISTRATION-ID",
            id="PAYLOAD-REGISTRY-REGISTER-DPP-RESPONSE-FIELD-REGISTRATION-ID",
        ),
    ],
)
def test_registry_response_uses_canonical_registration_id(contract_id: str) -> None:
    response = RegisterDppResponse.model_validate({"registryIdentifier": "R"})
    assert response.registrationId == "R"
    assert response.model_dump() == {"registrationId": "R"}


class _EncodingFailureCodec:
    def to_json(self, dpp: Any) -> str:
        raise ValueError("encode")

    def from_json(self, raw: str) -> Any:
        return raw


class _DecodingFailureCodec:
    def to_json(self, dpp: Any) -> str:
        return "{}"

    def from_json(self, raw: str) -> Any:
        raise ValueError("decode")


class _NullDecodingCodec:
    def to_json(self, dpp: Any) -> str:
        return "{}"

    def from_json(self, raw: str) -> Any:
        return None


class _NullEncodingCodec:
    def to_json(self, dpp: Any) -> Any:
        return None

    def from_json(self, raw: str) -> Any:
        return raw


def _make_generic_repo(handler: Any, codec: Any, validator: Any) -> DppRepoClient[Any]:
    return DppRepoClient(
        "http://repo.test",
        codec=codec,
        validator=validator,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_validator_failure_precedes_network_and_preserves_sdk_error() -> None:
    sent = False
    original = DppValidationClientError("already translated")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent = True
        return httpx.Response(200)

    def validator(value: Any) -> None:
        raise original

    with pytest.raises(DppValidationClientError) as exc:
        _make_generic_repo(handler, _EncodingFailureCodec(), validator).create_dpp(object())
    assert exc.value is original
    assert not sent


def test_codec_encoding_failure_precedes_network() -> None:
    sent = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent = True
        return httpx.Response(200)

    with pytest.raises(DppMappingClientError) as exc:
        _make_generic_repo(handler, _EncodingFailureCodec(), lambda value: None).create_dpp(
            object()
        )
    assert isinstance(exc.value.__cause__, ValueError)
    assert not sent


def test_codec_null_serialization_is_a_causal_mapping_error_before_network() -> None:
    sent = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent = True
        return httpx.Response(200)

    with pytest.raises(DppMappingClientError, match="serialization") as exc:
        _make_generic_repo(handler, _NullEncodingCodec(), lambda value: None).create_dpp(object())
    assert isinstance(exc.value.__cause__, ValueError)
    assert str(exc.value.__cause__) == "codec returned null JSON"
    assert not sent


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(httpx.ReadTimeout("timeout"), "timeout", id="timeout"),
        pytest.param(httpx.ConnectError("transport"), "transport", id="transport"),
    ],
)
def test_httpx_failures_become_network_errors_with_causes(error: Exception, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(DppNetworkClientError) as exc:
        _make_repo(handler).read_dpp_by_id("D")
    assert exc.value.__cause__ is error


def test_2xx_envelope_mapping_and_payload_failures_remain_mapping_errors() -> None:
    malformed = _make_repo(lambda request: httpx.Response(200, text="not-json"))
    with pytest.raises(DppMappingClientError) as malformed_error:
        malformed.read_dpp_by_id("D")
    assert malformed_error.value.__cause__ is not None

    missing_payload = _make_repo(
        lambda request: httpx.Response(200, json={"statusCode": "Success"})
    )
    with pytest.raises(DppMappingClientError, match="payload"):
        missing_payload.read_dpp_by_id("D")


def test_missing_api_status_is_a_causal_mapping_error() -> None:
    repo = _make_generic_repo(
        lambda request: httpx.Response(200, json={"payload": {}}),
        _NullDecodingCodec(),
        lambda value: None,
    )
    with pytest.raises(DppMappingClientError, match="statusCode") as exc:
        repo.read_dpp_by_id("D")
    assert isinstance(exc.value.__cause__, ValueError)
    assert str(exc.value.__cause__) == "Missing required response field: statusCode"


@pytest.mark.parametrize(
    ("missing_field", "operation"),
    [
        pytest.param(
            "payload",
            "read-dpp",
            id="required-payload-helper",
        ),
        pytest.param(
            "payload.dppId",
            "create-dpp-id",
            id="required-text-field-helper",
        ),
        pytest.param(
            "payload.dppIdentifiers",
            "read-dpp-identifiers",
            id="required-field-helper",
        ),
        pytest.param(
            "payload.registrationId",
            "registry-registration-id",
            id="registry-required-text-field-helper",
        ),
    ],
)
def test_synthesized_missing_structure_errors_have_meaningful_causes(
    missing_field: str,
    operation: str,
) -> None:
    if operation == "read-dpp":
        repo = _make_generic_repo(
            lambda request: httpx.Response(200, json={"statusCode": "Success"}),
            _NullDecodingCodec(),
            lambda value: None,
        )

        def call() -> None:
            repo.read_dpp_by_id("D")

    elif operation == "create-dpp-id":
        repo = _make_generic_repo(
            lambda request: httpx.Response(
                200, json={"statusCode": "SuccessCreated", "payload": {}}
            ),
            _NullDecodingCodec(),
            lambda value: None,
        )

        def call() -> None:
            repo.create_dpp(object())

    elif operation == "read-dpp-identifiers":
        repo = _make_generic_repo(
            lambda request: httpx.Response(200, json={"statusCode": "Success", "payload": {}}),
            _NullDecodingCodec(),
            lambda value: None,
        )

        def call() -> None:
            repo.read_dpp_ids_by_product_ids(["P"])

    else:
        registry = DppRegistryClient(
            "http://reg.test",
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json={"statusCode": "Success", "payload": {}}
                    )
                )
            ),
        )

        def call() -> None:
            registry.post_new_dpp_to_registry(RegisterDppRequest())

    with pytest.raises(DppMappingClientError, match=missing_field) as exc:
        call()
    assert isinstance(exc.value.__cause__, ValueError)
    assert str(exc.value.__cause__) == f"Missing required response field: {missing_field}"


def test_codec_decoding_failure_becomes_mapping_error_with_cause() -> None:
    repo = _make_generic_repo(
        lambda request: httpx.Response(200, json={"statusCode": "Success", "payload": {}}),
        _DecodingFailureCodec(),
        lambda value: None,
    )
    with pytest.raises(DppMappingClientError) as exc:
        repo.read_dpp_by_id("D")
    assert isinstance(exc.value.__cause__, ValueError)


def test_codec_null_result_is_a_causal_mapping_error_with_operation_context() -> None:
    repo = _make_generic_repo(
        lambda request: httpx.Response(200, json={"statusCode": "Success", "payload": {}}),
        _NullDecodingCodec(),
        lambda value: None,
    )
    with pytest.raises(DppMappingClientError, match="deserialization") as exc:
        repo.read_dpp_by_id("D")
    assert isinstance(exc.value.__cause__, ValueError)
    assert str(exc.value.__cause__) == "codec returned null DPP"


@pytest.mark.parametrize(
    "contract_id",
    [
        "CLIENT-VALIDATOR-PROTOCOL-001",
        "VALIDATION-CLIENT-DPP-DPP-VALIDATOR-88261F",
        "VALIDATION-CLIENT-DPP-VALIDATION-CLIENT-EXCEPTION-DPP-VALIDATION-CLIENT-EXCEPTION-99A38C",
    ],
)
def test_client_validation_contracts_are_callable_and_preserve_category(contract_id: str) -> None:
    original = DppValidationClientError("validation failed")

    def validator(value: object) -> None:
        raise original

    with pytest.raises(DppValidationClientError) as exc:
        _make_generic_repo(
            lambda request: httpx.Response(200), _EncodingFailureCodec(), validator
        ).create_dpp(object())
    assert exc.value is original


@pytest.mark.parametrize(
    ("contract_id", "error_type"),
    [
        ("ERROR-DPP-CLIENT-001", DppClientError),
        ("ERROR-DPP-MAPPING-CLIENT-001", DppMappingClientError),
        ("ERROR-DPP-NETWORK-CLIENT-001", DppNetworkClientError),
        ("ERROR-DPP-VALIDATION-CLIENT-001", DppValidationClientError),
        ("ERROR-MAPPING-001", DppMappingError),
    ],
)
def test_exception_contracts_expose_stable_categories(
    contract_id: str, error_type: type[Exception]
) -> None:
    error = error_type("contract context")
    assert str(error) == "contract context"
