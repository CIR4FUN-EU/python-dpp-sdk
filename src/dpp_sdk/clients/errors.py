"""Client exception hierarchy (port of ``dpp.*.client.exception``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .payloads import DppApiMessage, DppStatusCode


class DppClientError(Exception):
    """Base class for all DPP HTTP client errors."""


class DppValidationClientError(DppClientError):
    """Raised when a DPP fails validation before a request is sent."""


class DppMappingClientError(DppClientError):
    """Raised when request/response JSON cannot be serialized or parsed."""


class DppNetworkClientError(DppClientError):
    """Raised when the HTTP request cannot complete (connection/timeout)."""


class DppHttpClientError(DppClientError):
    """Raised when an endpoint returns a non-2xx HTTP status."""

    def __init__(self, message: str, status_code: int, response_body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DppApiClientError(DppClientError):
    """Raised when a 2xx response carries an error status in the API wrapper."""

    def __init__(
        self,
        message: str,
        status_code: DppStatusCode | None,
        messages: list[DppApiMessage] | None,
        raw_response_body: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.messages = messages
        self.raw_response_body = raw_response_body
