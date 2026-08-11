"""Regression coverage for supported Python-only client extensions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from dpp_sdk.clients import (
    DEFAULT_REGISTRY_BASE_URL,
    DEFAULT_REPO_BASE_URL,
    DppRegistryClient,
    DppRepoClient,
    local_registry_base_url,
    local_repo_base_url,
)
from dpp_sdk.clients._http import DEFAULT_CONNECT_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
from dpp_sdk.dpp4fun.model import Dpp4Fun
from dpp_sdk.dpp4fun.transport import Dpp4FunJsonCodec
from dpp_sdk.dpp4fun.validation import validate_dpp4fun


def _repo(client: httpx.Client | None = None) -> DppRepoClient[Dpp4Fun]:
    return DppRepoClient(
        "http://repo.test",
        Dpp4FunJsonCodec(),
        validate_dpp4fun,
        client=client,
    )


def _registry(client: httpx.Client | None = None) -> DppRegistryClient:
    return DppRegistryClient("http://registry.test", client=client)


@pytest.mark.parametrize(
    ("extension_id", "factory"),
    [
        pytest.param(
            "PYTHON-ONLY-CLIENT-LIFECYCLE-001-repo",
            _repo,
            id="PYTHON-ONLY-CLIENT-LIFECYCLE-001-repo",
        ),
        pytest.param(
            "PYTHON-ONLY-CLIENT-LIFECYCLE-001-registry",
            _registry,
            id="PYTHON-ONLY-CLIENT-LIFECYCLE-001-registry",
        ),
    ],
)
def test_sdk_owned_clients_close_idempotently_and_support_context_managers(
    extension_id: str, factory: Callable[[], Any]
) -> None:
    sdk_client = factory()
    assert sdk_client._client.timeout.connect == DEFAULT_CONNECT_TIMEOUT
    assert sdk_client._client.timeout.read == DEFAULT_REQUEST_TIMEOUT
    assert sdk_client._client.timeout.write == DEFAULT_REQUEST_TIMEOUT
    assert sdk_client._client.timeout.pool == DEFAULT_REQUEST_TIMEOUT

    with sdk_client as entered:
        assert entered is sdk_client
        assert not sdk_client._client.is_closed

    assert sdk_client._client.is_closed
    sdk_client.close()
    assert sdk_client._client.is_closed


@pytest.mark.parametrize(
    ("extension_id", "factory"),
    [
        pytest.param(
            "PYTHON-ONLY-CLIENT-LIFECYCLE-001-supplied-repo",
            _repo,
            id="PYTHON-ONLY-CLIENT-LIFECYCLE-001-supplied-repo",
        ),
        pytest.param(
            "PYTHON-ONLY-CLIENT-LIFECYCLE-001-supplied-registry",
            _registry,
            id="PYTHON-ONLY-CLIENT-LIFECYCLE-001-supplied-registry",
        ),
    ],
)
def test_caller_supplied_clients_remain_open_after_close_and_context_exit(
    extension_id: str, factory: Callable[[httpx.Client], Any]
) -> None:
    supplied = httpx.Client()
    sdk_client = factory(supplied)
    with sdk_client as entered:
        assert entered is sdk_client
    sdk_client.close()
    assert not supplied.is_closed
    supplied.close()


@pytest.mark.parametrize(
    ("extension_id", "factory"),
    [
        pytest.param(
            "PYTHON-ONLY-REPO-HEALTH-001",
            _repo,
            id="PYTHON-ONLY-REPO-HEALTH-001",
        ),
        pytest.param(
            "PYTHON-ONLY-REGISTRY-HEALTH-001",
            _registry,
            id="PYTHON-ONLY-REGISTRY-HEALTH-001",
        ),
    ],
)
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        pytest.param(httpx.Response(204), True, id="2xx"),
        pytest.param(httpx.Response(503), False, id="non-2xx"),
        pytest.param(httpx.ReadTimeout("timeout"), False, id="timeout"),
        pytest.param(httpx.ConnectError("transport"), False, id="transport"),
    ],
)
def test_health_helpers_return_reachability_without_raising(
    extension_id: str,
    factory: Callable[[httpx.Client], Any],
    outcome: httpx.Response | Exception,
    expected: bool,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/health"
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    sdk_client = factory(httpx.Client(transport=httpx.MockTransport(handler)))
    assert sdk_client.health_check() is expected


def test_local_endpoint_helpers_honor_defaults_ports_blank_values_and_url_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DPP_REPO_BASE_URL",
        "DPP_REGISTRY_BASE_URL",
        "DPP_REPO_PORT",
        "DPP_REGISTRY_PORT",
    ):
        monkeypatch.delenv(name, raising=False)
    assert local_repo_base_url() == DEFAULT_REPO_BASE_URL
    assert local_registry_base_url() == DEFAULT_REGISTRY_BASE_URL

    monkeypatch.setenv("DPP_REPO_PORT", "9100")
    monkeypatch.setenv("DPP_REGISTRY_PORT", "9101")
    assert local_repo_base_url() == "http://localhost:9100"
    assert local_registry_base_url() == "http://localhost:9101"

    monkeypatch.setenv("DPP_REPO_PORT", "   ")
    monkeypatch.setenv("DPP_REGISTRY_PORT", "   ")
    assert local_repo_base_url() == DEFAULT_REPO_BASE_URL
    assert local_registry_base_url() == DEFAULT_REGISTRY_BASE_URL

    monkeypatch.setenv("DPP_REPO_BASE_URL", " http://repo.override ")
    monkeypatch.setenv("DPP_REGISTRY_BASE_URL", "http://registry.override")
    assert local_repo_base_url() == "http://repo.override"
    assert local_registry_base_url() == "http://registry.override"


def test_local_factories_use_resolved_endpoint_without_starting_a_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://repo.local")
    monkeypatch.setenv("DPP_REGISTRY_BASE_URL", "http://registry.local")
    repo = DppRepoClient.for_local_mock(Dpp4FunJsonCodec(), validate_dpp4fun)
    registry = DppRegistryClient.for_local_mock()
    try:
        assert repo._base_url == "http://repo.local"
        assert registry._base_url == "http://registry.local"
    finally:
        repo.close()
        registry.close()
