"""Client exception hierarchy (port of ``dpp.*.client.exception``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .payloads import DppApiMessage, DppStatusCode


class DppClientError(Exception):
    """Base class for all DPP HTTP client errors."""


class DppMappingClientError(DppClientError):
    """Raised when request/response JSON cannot be serialized or parsed."""


class DppNetworkClientError(DppClientError):
    """Raised when the HTTP request cannot complete (connection/timeout)."""


class DppHttpClientError(DppClientError):
    """Raised when an endpoint returns an unstructured non-2xx HTTP status."""

    def __init__(self, message: str, status_code: int, response_body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DppApiClientError(DppClientError):
    """Raised when an API envelope reports failure, including structured HTTP errors."""

    def __init__(
        self,
        error_message: str,
        http_status: int,
        status_code: DppStatusCode,
        message: list[DppApiMessage] | None,
        raw_response_body: str,
    ) -> None:
        super().__init__(error_message)
        self.http_status = http_status
        self.status_code = status_code
        self.message = message
        self.raw_response_body = raw_response_body
