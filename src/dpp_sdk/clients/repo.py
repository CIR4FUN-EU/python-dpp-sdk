"""HTTP client for the DPP repository API (port of ``HttpDppRepoClient``).

Generic over a caller-owned DPP model type ``T``, mediated by a :class:`DppCodec`
(full-payload JSON) and a validator callable. Endpoint paths and the request
pipeline match the Java client exactly.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Generic, TypeVar

import httpx

from . import _http, endpoints
from .errors import DppMappingClientError, DppValidationClientError
from .payloads import CreateDppResponse, DeleteDppResponse, ReadDppIdsRequest, ReadDppIdsResponse

T = TypeVar("T")

_DPPS_PATH = "/dpps"
_DPPS_BY_PRODUCT_ID_PATH = "/dppsByProductId/"
_DPPS_BY_PRODUCT_ID_AND_DATE_PATH = "/dppsByProductIdAndDate/"
_DPPS_BY_PRODUCT_IDS_PATH = "/dppsByProductIds"


class DppRepoClient(Generic[T]):
    def __init__(
        self,
        base_url: str,
        codec: _http.DppCodec[T],
        validator: _http.DppValidator[T],
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = _http.normalize_base_url(base_url)
        self._codec = codec
        self._validator = validator
        self._client = client if client is not None else _http.build_client()

    @classmethod
    def for_local_mock(
        cls,
        codec: _http.DppCodec[T],
        validator: _http.DppValidator[T],
        *,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> DppRepoClient[T]:
        """Build a client pointed at the local mock repo (``dpp-sdk-demo``).

        Defaults to :func:`endpoints.local_repo_base_url` (``http://localhost:8080``,
        env-overridable); pass ``base_url`` to override.
        """
        resolved = base_url if base_url is not None else endpoints.local_repo_base_url()
        return cls(resolved, codec, validator, client=client)

    def health_check(self) -> bool:
        """Return ``True`` if the repo service answers ``GET /health`` with a 2xx."""
        return _http.probe_health(self._client, self._base_url)

    # --- lifecycle --------------------------------------------------------------
    def create_dpp(self, dpp: T) -> CreateDppResponse:
        try:
            self._validator(dpp)
        except Exception as exc:  # noqa: BLE001 - re-raised as a client error
            raise DppValidationClientError("DPP validation failed before request") from exc
        body = self._serialize(dpp)
        response = self._send("POST", _DPPS_PATH, body)
        payload = _http.require_payload(response)
        _http.require_text_field(payload, "dppId", "payload.dppId")
        return CreateDppResponse.model_validate(payload)

    def read_dpp_by_id(self, dpp_id: str) -> T:
        response = self._send("GET", self._dpp_path(dpp_id), None)
        return self._decode_dpp_payload(response)

    def read_dpp_by_product_id(self, product_id: str) -> T:
        path = _DPPS_BY_PRODUCT_ID_PATH + _http.encode_segment(product_id)
        response = self._send("GET", path, None)
        return self._decode_dpp_payload(response)

    def read_dpp_version_by_product_id_and_date(self, product_id: str, date: datetime) -> T:
        path = (
            _DPPS_BY_PRODUCT_ID_AND_DATE_PATH
            + _http.encode_segment(product_id)
            + "?date="
            + _http.encode_segment(date.isoformat())
        )
        response = self._send("GET", path, None)
        return self._decode_dpp_payload(response)

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], limit: int | None = None, cursor: str | None = None
    ) -> ReadDppIdsResponse:
        request_body = ReadDppIdsRequest(
            productIdentifiers=product_ids, limit=limit, cursor=cursor
        )
        response = self._send("POST", _DPPS_BY_PRODUCT_IDS_PATH, request_body.model_dump_json())
        payload = _http.require_payload(response)
        _http.require_field(payload, "dppIdentifiers", "payload.dppIdentifiers")
        return ReadDppIdsResponse.model_validate(payload)

    def update_dpp_by_id(self, dpp_id: str, partial_dpp: Any) -> T:
        body = json.dumps(partial_dpp)
        response = self._send("PATCH", self._dpp_path(dpp_id), body)
        return self._decode_dpp_payload(response)

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse:
        response = self._send("DELETE", self._dpp_path(dpp_id), None)
        return DeleteDppResponse(statusCode=response.statusCode, messages=response.messages)

    # --- fine-granular elements -------------------------------------------------
    def read_data_element(self, dpp_id: str, element_path: str) -> Any:
        response = self._send("GET", self._data_element_path(dpp_id, element_path), None)
        return _http.require_payload(response)

    def update_data_element(self, dpp_id: str, element_path: str, payload: Any) -> Any:
        body = json.dumps({"payload": payload})
        response = self._send("PATCH", self._data_element_path(dpp_id, element_path), body)
        return _http.require_payload(response)

    # --- internals --------------------------------------------------------------
    def _send(self, method: str, path: str, body: str | None) -> Any:
        return _http.request_api(self._client, method, _http.resolve(self._base_url, path), body)

    def _serialize(self, dpp: T) -> str:
        try:
            json_str = self._codec.to_json(dpp)
        except Exception as exc:  # noqa: BLE001 - re-raised as a client error
            raise DppMappingClientError("DPP serialization failed before request") from exc
        if json_str is None:
            raise DppMappingClientError("codec returned null JSON")
        return json_str

    def _decode_dpp_payload(self, response: Any) -> T:
        payload = _http.require_payload(response)
        payload_json = json.dumps(payload)
        try:
            return self._codec.from_json(payload_json)
        except Exception as exc:  # noqa: BLE001 - re-raised as a client error
            raise DppMappingClientError("DPP deserialization failed after response") from exc

    @staticmethod
    def _dpp_path(dpp_id: str) -> str:
        return _DPPS_PATH + "/" + _http.encode_segment(dpp_id)

    @classmethod
    def _data_element_path(cls, dpp_id: str, element_path: str) -> str:
        return cls._dpp_path(dpp_id) + "/elements/" + _http.encode_segment(element_path)
