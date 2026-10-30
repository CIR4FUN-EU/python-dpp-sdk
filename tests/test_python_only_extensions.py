"""Python-native synchronous HTTPX client ownership behavior."""

from __future__ import annotations

import httpx
import pytest

from dpp_sdk.clients import DppRegistryClient, DppRepoClient
from dpp_sdk.clients._http import DEFAULT_CONNECT_TIMEOUT, DEFAULT_REQUEST_TIMEOUT


@pytest.mark.parametrize("client_type", [DppRepoClient, DppRegistryClient])
def test_owned_http_clients_close_idempotently(client_type: type[object]) -> None:
    sdk_client = client_type("https://api.example")
    internal = sdk_client._client  # type: ignore[attr-defined]
    assert internal.timeout.connect == DEFAULT_CONNECT_TIMEOUT
    assert internal.timeout.read == DEFAULT_REQUEST_TIMEOUT
    with sdk_client as entered:  # type: ignore[attr-defined]
        assert entered is sdk_client
    assert internal.is_closed
    sdk_client.close()  # type: ignore[attr-defined]


@pytest.mark.parametrize("client_type", [DppRepoClient, DppRegistryClient])
def test_injected_httpx_client_remains_caller_owned(client_type: type[object]) -> None:
    supplied = httpx.Client()
    sdk_client = client_type("https://api.example", client=supplied)
    with sdk_client as entered:  # type: ignore[attr-defined]
        assert entered is sdk_client
    sdk_client.close()  # type: ignore[attr-defined]
    assert not supplied.is_closed
    supplied.close()
