"""API wrapper envelope and request/response DTOs for the DPP HTTP clients.

Ports ``dpp.repo.payloads.*`` and ``dpp.registry.payloads.*`` (which are
identical for the shared envelope) into a single module. These models use
``extra='ignore'`` to mirror the clients' Jackson config, which disables
``FAIL_ON_UNKNOWN_PROPERTIES``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DppStatusCode(StrEnum):
    """Application-level status in the API wrapper ``statusCode`` field."""

    Success = "Success"
    SuccessCreated = "SuccessCreated"
    SuccessAccepted = "SuccessAccepted"
    SuccessNoContent = "SuccessNoContent"
    ClientErrorBadRequest = "ClientErrorBadRequest"
    ClientNotAuthorized = "ClientNotAuthorized"
    ClientForbidden = "ClientForbidden"
    ClientMethodNotAllowed = "ClientMethodNotAllowed"
    ClientErrorResourceNotFound = "ClientErrorResourceNotFound"
    ClientResourceConflict = "ClientResourceConflict"
    ServerInternalError = "ServerInternalError"
    ServerErrorBadGateway = "ServerErrorBadGateway"

    @classmethod
    def _missing_(cls, value: object) -> DppStatusCode | None:
        # Mirror the Java @JsonCreator aliases.
        aliases = {
            "ClientErrorNotAuthorized": cls.ClientNotAuthorized,
            "ClientErrorForbidden": cls.ClientForbidden,
        }
        if isinstance(value, str):
            return aliases.get(value)
        return None

    @property
    def is_success(self) -> bool:
        return self in {
            DppStatusCode.Success,
            DppStatusCode.SuccessCreated,
            DppStatusCode.SuccessAccepted,
            DppStatusCode.SuccessNoContent,
        }


class MessageType(StrEnum):
    """Severity/category for API wrapper messages."""

    Info = "Info"
    Warning = "Warning"
    Error = "Error"
    Exception = "Exception"


class _ClientBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class DppApiMessage(_ClientBase):
    messageType: MessageType | None = None
    text: str | None = None
    code: str | None = None
    correlationId: str | None = None
    timestamp: datetime | None = None


class DppApiResponse(_ClientBase):
    """Standard response envelope; ``payload`` is left as raw JSON (``Any``)."""

    statusCode: DppStatusCode | None = None
    payload: Any = None
    messages: list[DppApiMessage] | None = None


# --- repository DTOs ------------------------------------------------------------
class CreateDppResponse(_ClientBase):
    dppId: str | None = None


class DeleteDppResponse(_ClientBase):
    statusCode: DppStatusCode | None = None
    messages: list[DppApiMessage] | None = None


class ReadDppIdsRequest(_ClientBase):
    productIdentifiers: list[str] | None = None
    limit: int | None = None
    cursor: str | None = None


class ReadDppIdsResponse(_ClientBase):
    dppIdentifiers: list[str] | None = None
    nextCursor: str | None = None


class UpdateDataElementRequest(_ClientBase):
    payload: Any = None


# --- registry DTOs --------------------------------------------------------------
class RegisterDppRequest(_ClientBase):
    productIdentifier: str | None = None
    dppIdentifier: str | None = None
    operatorIdentifier: str | None = None
    repoUrl: str | None = None


class RegisterDppResponse(_ClientBase):
    registryIdentifier: str | None = None
