"""HTTP client for the DPP registry API (port of ``HttpDppRegistryClient``)."""

from __future__ import annotations

from types import TracebackType
from typing import Self

import httpx
from pydantic import ValidationError

from . import _http, endpoints
from .errors import DppMappingClientError
from .payloads import RegisterDppRequest, RegisterDppResponse

_REGISTER_PATH = "/v1/registerDPP"


class DppRegistryClient:
    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self._base_url = _http.normalize_base_url(base_url)
        self._owns_client = client is None
        self._client = client if client is not None else _http.build_client()
        self._closed = False

    @classmethod
    def for_local_mock(
        cls,
        *,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> DppRegistryClient:
        """Build a client for a configurable local registry endpoint.

        Defaults to :func:`endpoints.local_registry_base_url`; pass ``base_url`` to override.
        """
        resolved = base_url if base_url is not None else endpoints.local_registry_base_url()
        return cls(resolved, client=client)

    def health_check(self) -> bool:
        """Return ``True`` if the registry service answers ``GET /health`` with a 2xx."""
        return _http.probe_health(self._client, self._base_url)

    def close(self) -> None:
        """Close the internally created HTTPX client, if this SDK instance owns it."""
        if self._owns_client and not self._closed:
            self._client.close()
            self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> RegisterDppResponse:
        body = request.model_dump_json()
        response = _http.request_api(
            self._client, "POST", _http.resolve(self._base_url, _REGISTER_PATH), body
        )
        payload = _http.require_payload(response)
        try:
            result = RegisterDppResponse.model_validate(payload)
        except ValidationError as exc:
            raise DppMappingClientError("Registry response could not be mapped") from exc
        _http.require_text_field(
            {"registrationId": result.registrationId}, "registrationId", "payload.registrationId"
        )
        return result
