"""Shared synchronous HTTP and API-envelope handling."""

from __future__ import annotations

import json
import re
from typing import Any, NoReturn
from urllib.parse import quote, urlsplit

import httpx
from pydantic import ValidationError

from .errors import (
    DppApiClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
)
from .payloads import DppApiResponse, DppStatusCode

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_REQUEST_TIMEOUT = 15.0


def build_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(DEFAULT_REQUEST_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)
    )


def normalize_base_url(base_url: str) -> str:
    trimmed = base_url.strip()
    if not trimmed:
        raise ValueError("baseUrl must not be blank")
    try:
        parsed = urlsplit(trimmed)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("baseUrl must be a valid URI") from exc
    if (
        re.search(r"%(?![0-9A-Fa-f]{2})", trimmed)
        or any(char in trimmed for char in '<>"{}|\\^`')
        or any(ord(char) <= 0x20 for char in trimmed)
    ):
        raise ValueError("baseUrl must be a valid URI")
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or host is None
        or (port is not None and not 0 <= port <= 65535)
        or "?" in trimmed
        or "#" in trimmed
    ):
        raise ValueError(
            "baseUrl must be an absolute HTTP(S) URL with a host and no query/fragment"
        )
    return trimmed.rstrip("/")


def resolve(base_url: str, path_and_query: str) -> str:
    path = path_and_query or "/"
    return base_url + (path if path.startswith("/") else f"/{path}")


def encode_segment(value: str) -> str:
    return quote(value, safe="*").replace("~", "%7E")


def serialize_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DppMappingClientError("Client JSON serialization failed before request") from exc


def request_api(
    client: httpx.Client,
    method: str,
    url: str,
    body: str | None,
    *,
    allow_no_content: bool = False,
) -> DppApiResponse:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        response = client.request(method, url, content=body, headers=headers)
    except httpx.TimeoutException as exc:
        raise DppNetworkClientError("DPP HTTP request timed out") from exc
    except httpx.TransportError as exc:
        raise DppNetworkClientError("DPP HTTP request could not complete") from exc

    if not 200 <= response.status_code < 300:
        _raise_http(response.status_code, response.text)
    if response.status_code == 204 and allow_no_content:
        return DppApiResponse(status_code=DppStatusCode.SuccessNoContent)
    api_response = parse_response(response.text)
    _require_success(api_response, response.text)
    return api_response


def parse_response(raw_body: str) -> DppApiResponse:
    try:
        return DppApiResponse.model_validate_json(raw_body)
    except (ValidationError, ValueError) as exc:
        raise DppMappingClientError("DPP API response could not be mapped") from exc


def _raise_http(status: int, raw_body: str) -> None:
    try:
        api_response = parse_response(raw_body)
        if api_response.status_code is None or api_response.status_code.is_success:
            raise ValueError("Error response has no error statusCode")
    except DppMappingClientError as exc:
        raise DppHttpClientError(
            f"DPP endpoint returned non-success HTTP status {status}", status, raw_body
        ) from exc
    except ValueError as exc:
        raise DppHttpClientError(
            f"DPP endpoint returned non-success HTTP status {status}", status, raw_body
        ) from exc
    raise DppApiClientError(
        f"DPP endpoint returned HTTP {status}",
        status,
        api_response.status_code,
        api_response.message,
        raw_body,
    )


def _require_success(response: DppApiResponse, raw_body: str) -> None:
    if response.status_code is None:
        cause = ValueError("Missing statusCode")
        raise DppMappingClientError("DPP API response could not be mapped") from cause
    if not response.status_code.is_success:
        raise DppApiClientError(
            f"DPP API returned error status {response.status_code.value}",
            -1,
            response.status_code,
            response.message,
            raw_body,
        )


def require_payload(response: DppApiResponse) -> Any:
    if response.payload is None:
        _missing_field("payload")
    return response.payload


def require_field(payload: Any, field_name: str, field_path: str) -> Any:
    if not isinstance(payload, dict) or payload.get(field_name) is None:
        _missing_field(field_path)
    return payload[field_name]


def require_text_field(payload: Any, field_name: str, field_path: str) -> str:
    value = require_field(payload, field_name, field_path)
    if not isinstance(value, str) or not value.strip():
        _missing_field(field_path)
    return value


def _missing_field(field_path: str) -> NoReturn:
    message = f"Missing required response field: {field_path}"
    raise DppMappingClientError(message) from ValueError(message)
