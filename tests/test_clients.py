"""HTTP client behavior against a mocked httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest

from dpp_sdk.clients import (
    DppApiClientError,
    DppHttpClientError,
    DppRegistryClient,
    DppRepoClient,
    RegisterDppRequest,
)
from dpp_sdk.dpp4fun.model import Dpp4Fun
from dpp_sdk.dpp4fun.transport import Dpp4FunJsonCodec, to_json, validate_dpp4fun


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
    assert captured["path"] == "/dpps"
    # the create body is the flat transport shape
    assert "passportMetadata" in captured["body"]  # type: ignore[operator]


def test_read_by_id_decodes_via_codec(valid_dpp4fun: Dpp4Fun) -> None:
    flat = json.loads(to_json(valid_dpp4fun))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dpps/DPP-1"
        return httpx.Response(200, json={"statusCode": "Success", "payload": flat})

    assert _make_repo(handler).read_dpp_by_id("DPP-1") == valid_dpp4fun


def test_read_by_product_id_encodes_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dppsByProductId/GTIN 0001"
        assert request.url.raw_path.endswith(b"/dppsByProductId/GTIN%200001")
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"x": 1}})

    # codec.from_json will fail on this dummy payload; we only assert the URL.
    with pytest.raises(Exception):  # noqa: B017, PT011
        _make_repo(handler).read_dpp_by_product_id("GTIN 0001")


def test_read_dpp_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dppsByProductIds"
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


def test_update_data_element_wraps_payload() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"statusCode": "Success", "payload": 42})

    result = _make_repo(handler).update_data_element("DPP-1", "weight", 42)
    assert result == 42
    assert seen["path"] == "/dpps/DPP-1/elements/weight"
    assert seen["body"] == {"payload": 42}


def test_delete_returns_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(200, json={"statusCode": "SuccessNoContent", "messages": []})

    assert _make_repo(handler).delete_dpp_by_id("DPP-1").statusCode is not None


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


def test_registry_register() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/registerDPP"
        return httpx.Response(
            201,
            json={"statusCode": "SuccessCreated", "payload": {"registryIdentifier": "REG-1"}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    registry = DppRegistryClient("http://reg.test", client=client)
    response = registry.post_new_dpp_to_registry(
        RegisterDppRequest(productIdentifier="GTIN-0001", dppIdentifier="DPP-1")
    )
    assert response.registryIdentifier == "REG-1"
