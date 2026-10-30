"""Generic JSON client for the final repository API."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from . import _http
from .errors import DppMappingClientError
from .payloads import (
    CreateDppResponse,
    DeleteDppResponse,
    DppApiResponse,
    DppRepresentation,
    ReadDppIdsRequest,
    ReadDppIdsResponse,
)

_DPPS = "/v1/dpps"


class DppRepoClient:
    """Synchronous JSON in/JSON out client for repository operations."""

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

    def create_dpp(
        self, dpp: Any, representation: DppRepresentation | None = DppRepresentation.COMPRESSED
    ) -> CreateDppResponse:
        representation = _selected(representation)
        envelope = self._send(
            "POST", _DPPS + representation.query_suffix, _http.serialize_json(_required(dpp))
        )
        payload = envelope.payload
        if payload is None:
            return CreateDppResponse(status_code=envelope.status_code, message=envelope.message)
        if not isinstance(payload, dict):
            raise _mapping_error("payload")
        identifier = payload.get("digitalProductPassportId")
        if identifier is not None and (not isinstance(identifier, str) or not identifier.strip()):
            raise _mapping_error("payload.digitalProductPassportId")
        return CreateDppResponse(
            status_code=envelope.status_code,
            message=envelope.message,
            digital_product_passport_id=identifier,
        )

    def read_dpp_by_id(
        self, dpp_id: str, representation: DppRepresentation | None = DppRepresentation.COMPRESSED
    ) -> DppApiResponse:
        return self._send(
            "GET", self._dpp_path(dpp_id) + _selected(representation).query_suffix, None
        )

    def read_dpp_by_product_id(
        self,
        product_id: str,
        representation: DppRepresentation | None = DppRepresentation.COMPRESSED,
    ) -> DppApiResponse:
        path = (
            "/v1/dppsByProductId/" + _segment(product_id) + _selected(representation).query_suffix
        )
        return self._send("GET", path, None)

    def read_dpp_version_by_id_and_date(
        self,
        dpp_id: str,
        date: datetime,
        representation: DppRepresentation | None = DppRepresentation.COMPRESSED,
    ) -> DppApiResponse:
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError("date must be timezone-aware")
        instant = date.astimezone(UTC)
        date_text = instant.isoformat().replace("+00:00", "Z")
        query = "?date=" + quote(date_text, safe="")
        if _selected(representation) is DppRepresentation.FULL:
            query += "&representation=full"
        return self._send("GET", "/v1/dppsByIdAndDate/" + _segment(dpp_id) + query, None)

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], limit: int | None = None, cursor: str | None = None
    ) -> ReadDppIdsResponse:
        request = ReadDppIdsRequest(product_identifiers=product_ids, limit=limit, cursor=cursor)
        response = self._send(
            "POST",
            "/v1/dppsByProductIds",
            request.model_dump_json(by_alias=True, exclude_none=False),
        )
        payload = _http.require_payload(response)
        _http.require_field(payload, "dppIdentifiers", "payload.dppIdentifiers")
        try:
            return ReadDppIdsResponse.model_validate(
                {**payload, "statusCode": response.status_code, "message": response.message}
            )
        except (ValidationError, TypeError) as exc:
            raise DppMappingClientError("DPP identifier response could not be mapped") from exc

    def update_dpp_by_id(
        self,
        dpp_id: str,
        partial_dpp: Any,
        representation: DppRepresentation | None = DppRepresentation.COMPRESSED,
    ) -> DppApiResponse:
        body = _http.serialize_json(_required(partial_dpp))
        return self._send(
            "PATCH", self._dpp_path(dpp_id) + _selected(representation).query_suffix, body
        )

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
        response = self._send("DELETE", self._dpp_path(dpp_id), None)
        return DeleteDppResponse(status_code=response.status_code, message=response.message)

    def read_data_element(
        self,
        dpp_id: str,
        element_id_path: str,
        representation: DppRepresentation | None = DppRepresentation.COMPRESSED,
    ) -> DppApiResponse:
        return self._element_request("GET", dpp_id, element_id_path, None, representation)

    def update_data_element(
        self,
        dpp_id: str,
        element_id_path: str,
        data_element: Any,
        representation: DppRepresentation = DppRepresentation.COMPRESSED,
    ) -> DppApiResponse:
        return self._element_request(
            "PATCH",
            dpp_id,
            element_id_path,
            _http.serialize_json(_required(data_element)),
            representation,
        )

    def _element_request(
        self,
        method: str,
        dpp_id: str,
        element_id_path: str,
        body: str | None,
        representation: DppRepresentation | None,
    ) -> DppApiResponse:
        if not element_id_path.strip():
            raise ValueError("elementIdPath must not be blank")
        response = self._send(
            method,
            self._dpp_path(dpp_id)
            + "/elements/"
            + _segment(element_id_path)
            + _selected(representation).query_suffix,
            body,
        )
        _http.require_payload(response)
        return response

    def _send(self, method: str, path: str, body: str | None) -> DppApiResponse:
        return _http.request_api(
            self._client,
            method,
            _http.resolve(self._base_url, path),
            body,
            allow_no_content=True,
        )

    @staticmethod
    def _dpp_path(dpp_id: str) -> str:
        return _DPPS + "/" + _segment(dpp_id)


def _required(value: Any) -> Any:
    if value is None:
        raise TypeError("JSON value must not be null")
    return value


def _segment(value: str) -> str:
    return _http.encode_segment(value)


def _selected(representation: DppRepresentation | None) -> DppRepresentation:
    return representation or DppRepresentation.COMPRESSED


def _mapping_error(path: str) -> DppMappingClientError:
    message = f"Missing required response field: {path}"
    return DppMappingClientError(message)
