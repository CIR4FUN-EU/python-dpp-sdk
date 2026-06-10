"""HTTP client for the DPP registry API (port of ``HttpDppRegistryClient``)."""

from __future__ import annotations

import httpx

from . import _http, endpoints
from .payloads import RegisterDppRequest, RegisterDppResponse

_REGISTER_PATH = "/registerDPP"


class DppRegistryClient:
    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self._base_url = _http.normalize_base_url(base_url)
        self._client = client if client is not None else _http.build_client()

    @classmethod
    def for_local_mock(
        cls,
        *,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> DppRegistryClient:
        """Build a client pointed at the local mock registry (``dpp-sdk-demo``).

        Defaults to :func:`endpoints.local_registry_base_url`
        (``http://localhost:8081``, env-overridable); pass ``base_url`` to override.
        """
        resolved = (
            base_url if base_url is not None else endpoints.local_registry_base_url()
        )
        return cls(resolved, client=client)

    def health_check(self) -> bool:
        """Return ``True`` if the registry service answers ``GET /health`` with a 2xx."""
        return _http.probe_health(self._client, self._base_url)

    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> RegisterDppResponse:
        body = request.model_dump_json()
        response = _http.request_api(
            self._client, "POST", _http.resolve(self._base_url, _REGISTER_PATH), body
        )
        payload = _http.require_payload(response)
        _http.require_text_field(payload, "registryIdentifier", "payload.registryIdentifier")
        return RegisterDppResponse.model_validate(payload)
