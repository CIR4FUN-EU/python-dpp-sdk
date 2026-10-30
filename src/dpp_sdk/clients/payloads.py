"""Neutral request and response JSON contracts for repository and registry APIs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class DppStatusCode(StrEnum):
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
    ServerNotImplemented = "ServerNotImplemented"
    ServerInternalError = "ServerInternalError"
    ServerErrorBadGateway = "ServerErrorBadGateway"

    @property
    def is_success(self) -> bool:
        return self in {
            self.Success,
            self.SuccessCreated,
            self.SuccessAccepted,
            self.SuccessNoContent,
        }


class MessageType(StrEnum):
    Info = "Info"
    Warning = "Warning"
    Error = "Error"
    Exception = "Exception"


class DppRepresentation(StrEnum):
    COMPRESSED = "compressed"
    FULL = "full"

    @classmethod
    def from_query(cls, value: str | None) -> DppRepresentation:
        if value is None or value.lower() == "compressed":
            return cls.COMPRESSED
        if value.lower() == "full":
            return cls.FULL
        raise ValueError("representation must be full or compressed")

    @property
    def query_suffix(self) -> str:
        return "?representation=full" if self is self.FULL else ""


class _Payload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class DppApiMessage(_Payload):
    message_type: MessageType = Field(alias="messageType")
    text: str
    code: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId")
    timestamp: AwareDatetime | None = None


class DppApiResponse(_Payload):
    status_code: DppStatusCode | None = Field(default=None, alias="statusCode")
    payload: Any = None
    message: list[DppApiMessage] | None = None


class CreateDppResponse(_Payload):
    status_code: DppStatusCode | None = Field(default=None, alias="statusCode")
    message: list[DppApiMessage] | None = None
    digital_product_passport_id: str | None = Field(default=None, alias="digitalProductPassportId")


class DeleteDppResponse(_Payload):
    status_code: DppStatusCode | None = Field(default=None, alias="statusCode")
    message: list[DppApiMessage] | None = None


class ReadDppIdsRequest(_Payload):
    product_identifiers: list[str] | None = Field(default=None, alias="productIdentifiers")
    limit: int | None = None
    cursor: str | None = None


class ReadDppIdsResponse(_Payload):
    status_code: DppStatusCode | None = Field(default=None, alias="statusCode")
    message: list[DppApiMessage] | None = None
    dpp_identifiers: list[str] = Field(alias="dppIdentifiers")
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class RegisterDppRequest(_Payload):
    unique_product_identifier: str | None = Field(default=None, alias="uniqueProductIdentifier")
    digital_product_passport_id: str | None = Field(default=None, alias="digitalProductPassportId")
    unique_economic_operator_identifier: str | None = Field(
        default=None, alias="uniqueEconomicOperatorIdentifier"
    )
    dpp_api_endpoint: str | None = Field(default=None, alias="dppApiEndpoint")


class RegisterDppResponse(_Payload):
    status_code: DppStatusCode | None = Field(default=None, alias="statusCode")
    message: list[DppApiMessage] | None = None
    registration_id: str | None = Field(default=None, alias="registrationId")
