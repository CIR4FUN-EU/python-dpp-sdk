"""Shared HTTP transport and JSON helpers (port of ``HttpSupport``).

Provides base-URL handling, URL encoding, the request/parse/validate pipeline for
the API wrapper envelope, and the ``DppCodec`` / ``DppValidator`` typing contracts.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from .errors import (
    DppApiClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
)
from .payloads import DppApiResponse

T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_REQUEST_TIMEOUT = 15.0


class DppCodec(Protocol[T]):
    """Converts a caller-owned DPP type to and from full JSON payloads."""

    def to_json(self, dpp: T) -> str: ...

    def from_json(self, raw: str) -> T: ...


class DppValidator(Protocol[T_contra]):
    """Validates a caller-owned DPP type before a create request is sent."""

    def __call__(self, dpp: T_contra) -> None: ...


def build_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(DEFAULT_REQUEST_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    )


def normalize_base_url(base_url: str) -> str:
    trimmed = base_url.strip()
    if not trimmed:
        raise ValueError("baseUrl must not be blank")
    return trimmed.rstrip("/")


def resolve(base_url: str, path_and_query: str) -> str:
    normalized = path_and_query if path_and_query else "/"
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return base_url + normalized


def encode_segment(value: str) -> str:
    return quote(value, safe="*").replace("~", "%7E")


def probe_health(client: httpx.Client, base_url: str) -> bool:
    """Probe ``GET {base_url}/health`` and report reachability.

    Mirrors the Java ``DemoServicePreflight.probe``: returns ``True`` only on a 2xx
    response and ``False`` on any non-2xx status or transport/timeout error. The mock
    ``/health`` endpoint returns a bare ``HealthPayload`` (not the wrapped DPP API
    envelope), so this deliberately bypasses :func:`request_api`.
    """
    url = resolve(normalize_base_url(base_url), "/health")
    try:
        response = client.request("GET", url, headers={"Accept": "application/json"})
    except (httpx.TimeoutException, httpx.TransportError):
        return False
    return 200 <= response.status_code < 300


def request_api(
    client: httpx.Client,
    method: str,
    url: str,
    body: str | None,
) -> DppApiResponse:
    """Run the full request pipeline and return a validated success envelope."""
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        response = client.request(method, url, content=body, headers=headers)
    except httpx.TimeoutException as exc:
        raise DppNetworkClientError("DPP HTTP request timed out") from exc
    except httpx.TransportError as exc:
        raise DppNetworkClientError("DPP HTTP request could not complete") from exc

    _require_http_success(response)
    api_response = _parse_api_response(response.text)
    _require_api_success(api_response, response.text)
    return api_response


def _require_http_success(response: httpx.Response) -> None:
    if not 200 <= response.status_code < 300:
        raise DppHttpClientError(
            f"DPP endpoint returned non-success HTTP status {response.status_code}",
            response.status_code,
            response.text,
        )


def _parse_api_response(raw_body: str) -> DppApiResponse:
    try:
        return DppApiResponse.model_validate_json(raw_body)
    except ValidationError as exc:
        raise DppMappingClientError("DPP API response could not be mapped") from exc


def _require_api_success(response: DppApiResponse, raw_body: str) -> None:
    status_code = response.statusCode
    if status_code is None:
        cause = ValueError("Missing required response field: statusCode")
        raise DppMappingClientError(
            "DPP API response could not be mapped: missing statusCode"
        ) from cause
    if not status_code.is_success:
        raise DppApiClientError(
            f"DPP API returned error status {status_code.value}",
            status_code,
            response.messages,
            raw_body,
        )


def require_payload(response: DppApiResponse) -> Any:
    payload = response.payload
    if payload is None:
        raise _missing_field("payload")
    return payload


def require_text_field(payload: Any, field_name: str, field_path: str) -> str:
    if not isinstance(payload, dict):
        raise _missing_field(field_path)
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise _missing_field(field_path)
    return value


def require_field(payload: Any, field_name: str, field_path: str) -> Any:
    if not isinstance(payload, dict) or payload.get(field_name) is None:
        raise _missing_field(field_path)
    return payload[field_name]


def _missing_field(field_path: str) -> DppMappingClientError:
    message = f"Missing required response field: {field_path}"
    error = DppMappingClientError(message)
    error.__cause__ = ValueError(message)
    return error
