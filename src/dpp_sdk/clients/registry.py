"""Generic JSON client for the final registry API."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import ValidationError

from . import _http
from .errors import DppMappingClientError
from .payloads import RegisterDppRequest, RegisterDppResponse


class DppRegistryClient:
    """Synchronous JSON in/JSON out client for registry registration."""

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self._base_url = _http.normalize_base_url(base_url)
        self._owns_client = client is None
        self._client = client if client is not None else _http.build_client()
        self._closed = False

    def close(self) -> None:
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

    def post_new_dpp_to_registry(
        self, request: RegisterDppRequest | dict[str, Any]
    ) -> RegisterDppResponse:
        if request is None:
            raise DppMappingClientError(
                "DPP registry request could not be mapped before request"
            ) from ValueError("request must not be null")
        body = (
            request.model_dump_json(by_alias=True, exclude_none=False)
            if isinstance(request, RegisterDppRequest)
            else _http.serialize_json(request)
        )
        response = _http.request_api(
            self._client, "POST", _http.resolve(self._base_url, "/v1/registerDPP"), body
        )
        payload = response.payload
        if payload is None:
            return RegisterDppResponse(status_code=response.status_code, message=response.message)
        if not isinstance(payload, dict):
            raise _missing_registry_payload()
        registration_id = payload.get("registrationId")
        if registration_id is not None and (
            not isinstance(registration_id, str) or not registration_id.strip()
        ):
            raise _missing_registry_payload()
        try:
            return RegisterDppResponse(
                status_code=response.status_code,
                message=response.message,
                registration_id=registration_id,
            )
        except ValidationError as exc:
            raise DppMappingClientError("Registry response could not be mapped") from exc


def _missing_registry_payload() -> DppMappingClientError:
    message = "Missing required response field: payload"
    return DppMappingClientError(message)
