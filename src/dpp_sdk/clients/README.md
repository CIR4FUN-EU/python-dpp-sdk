# DPP SDK clients module

## Purpose and scope

Use dpp_sdk.clients to call public repository and registry APIs synchronously. DppRepoClient[T] uses a caller-supplied codec and validator for a complete passport of type T; DppRegistryClient registers metadata only. This is the canonical owner for client routes, payloads, response envelopes, and client errors. The [SDK usage guide](../../../docs/usage.md) owns the walkthrough and the [model guide](../../../docs/model-guide.md) owns full DPP field definitions.

The module does not run a service or provide authentication, retries, async clients, persistence, internal registry APIs, lifecycle storage, or Docker runtime support.

## Request flow and prerequisites

![Python client request flow](../../../docs/architecture/python-client-request-flow.svg)

*Diagram: repository calls carry complete/partial DPP data; registry calls carry registration metadata. Both call a URL supplied by the application.*

Create a repository client with a base URL, DppCodec[T], and validator. The built-in furniture pair is Dpp4FunJsonCodec() and validate_dpp4fun. A client-created HTTPX client is closed by close() or the with block; an injected client remains caller-owned.

~~~python
from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppRepoClient

with DppRepoClient("https://repo.example.com", Dpp4FunJsonCodec(), validate_dpp4fun) as repository:
    assert repository.health_check() is True
~~~

All API calls use Accept: application/json; calls with a body additionally use Content-Type: application/json. Dynamic DPP IDs, product IDs, dates, and element paths are percent-encoded. The complete API response uses the following envelope, except health probes, which consume a bare service response.

## Shared response envelope, DTOs, and errors

| Envelope field | Type and null behavior | Client behavior |
| --- | --- | --- |
| statusCode | DppStatusCode or null | Required by normal API calls. Success, SuccessCreated, SuccessAccepted, and SuccessNoContent are successful. Missing/unrecognized is mapping failure. ClientErrorNotAuthorized and ClientErrorForbidden are accepted input aliases. |
| payload | JSON value or null | Required for value-returning operations. A missing/null required payload raises DppMappingClientError. Delete does not require it. |
| messages | list[DppApiMessage] or null | Each message may contain nullable messageType, text, code, correlationId, and timestamp. |

DppApiResponse, DppApiMessage, CreateDppResponse, DeleteDppResponse, ReadDppIdsRequest, ReadDppIdsResponse, RegisterDppRequest, and RegisterDppResponse ignore unknown input fields. The response envelope is parsed before an operation-specific payload is read.

| Error | When it is raised |
| --- | --- |
| DppValidationClientError | The supplied validator rejects a complete DPP before create_dpp() sends a request. |
| DppMappingClientError | Request serialization, malformed/incomplete envelope, missing required payload field, or full-payload codec mapping fails; the originating error is retained as a cause where applicable. |
| DppNetworkClientError | HTTPX transport or timeout failure on a normal API call. |
| DppHttpClientError | A normal API call returns non-2xx HTTP; it exposes status_code and response_body. |
| DppApiClientError | A 2xx response envelope carries a non-success statusCode; it exposes parsed status, messages, and raw body. |

## Repository operation reference

Every normal API operation below accepts any 2xx HTTP response only when its envelope has a successful statusCode. “Shared errors” means the preceding error table applies.

### health_check

**Purpose:** repository reachability. **Signature:** health_check() -> bool. **HTTP:** GET /health; no path/query/body and Accept only. **Success/response:** any 2xx returns True; non-2xx, timeout, and transport failure return False. The bare health body is not parsed as an API envelope. **Null/errors:** not applicable; it never raises client HTTP/network errors. **Limit:** reachability does not guarantee later API success. **Evidence:** repo.py:DppRepoClient.health_check; _http.py:probe_health; `tests/test_python_only_extensions.py:test_health_helpers_return_reachability_without_raising`.

### create_dpp

**Purpose:** validate and create a complete passport. **Signature:** create_dpp(dpp: T) -> CreateDppResponse. **HTTP:** POST /v1/dpps; no path/query.

| Request | Definition |
| --- | --- |
| Body type | Non-null JSON string from the supplied DppCodec.to_json(dpp), after the supplied validator passes. |
| Fields/example | The caller codec owns the full-DPP field table; use the [model guide](../../../docs/model-guide.md). |
| Null/mapping behavior | Validator failure becomes DppValidationClientError. Codec failure or null output becomes DppMappingClientError before I/O. |

| Success response field | Definition |
| --- | --- |
| Envelope | Successful statusCode and non-null object payload. |
| dppId | CreateDppResponse field, nullable in its DTO but required non-blank by this client method. |

~~~json
{"statusCode":"SuccessCreated","payload":{"dppId":"DPP-1"},"messages":null}
~~~

**Limit:** no domain schema beyond the caller codec. **Errors:** shared errors plus the request rules above. **Evidence:** repo.py:create_dpp; _http.py:require_text_field; test_create_returns_dpp_id; test_validator_failure_precedes_network_and_preserves_sdk_error.

### read_dpp_by_id

**Purpose:** full typed passport by DPP ID. **Signature:** read_dpp_by_id(dpp_id: str) -> T. **HTTP:** GET /v1/dpps/{dppId}?representation=full.

| Parameters and request | Definition |
| --- | --- |
| dppId path | Required non-blank str; percent-encoded. |
| query/body | representation=full; no body. |
| success response | Successful envelope with required non-null full JSON payload; the caller codec decodes it to T. |

~~~json
{"statusCode":"Success","payload":{"callerCodecOwned":"full DPP JSON"},"messages":null}
~~~

**Null/errors:** null payload or codec failure is DppMappingClientError; shared errors apply. **Limit:** full-DPP fields are owned by the caller codec. **Evidence:** repo.py:read_dpp_by_id; test_read_by_id_decodes_via_codec.

### read_dpp_by_product_id

**Purpose:** full typed passport by product ID. **Signature:** read_dpp_by_product_id(product_id: str) -> T. **HTTP:** GET /v1/dppsByProductId/{productId}?representation=full.

| Parameters and request | Definition |
| --- | --- |
| productId path | Required non-blank str; percent-encoded. |
| query/body | representation=full; no body. |
| success response | Successful envelope with required non-null full JSON payload decoded to T by the caller codec. |

~~~json
{"statusCode":"Success","payload":{"callerCodecOwned":"full DPP JSON"},"messages":null}
~~~

**Null/errors:** null payload or codec failure is mapping failure; shared errors apply. **Limit:** full representation only. **Evidence:** repo.py:read_dpp_by_product_id; test_read_by_product_id_encodes_path.

### read_compressed_dpp_by_id

**Purpose:** raw project-defined compressed representation. **Signature:** read_compressed_dpp_by_id(dpp_id: str) -> Any. **HTTP:** GET /v1/dpps/{dppId}?representation=compressed.

| Parameters and request | Definition |
| --- | --- |
| dppId path | Required non-blank str; percent-encoded. |
| query/body | representation=compressed; no body. |
| success response | Successful envelope with required non-null raw JSON payload, returned without codec conversion. |

~~~json
{"statusCode":"Success","payload":{"format":"service-defined"},"messages":null}
~~~

**Null/errors:** null payload is mapping failure; shared errors apply. **Limit:** no decompression or typed Dpp4Fun conversion. **Evidence:** repo.py:read_compressed_dpp_by_id; test_read_compressed_dpp_returns_raw_payload_without_codec.

### read_dpp_version_by_id_and_date

**Purpose:** full historical version by DPP ID and instant. **Signature:** read_dpp_version_by_id_and_date(dpp_id: str, date: datetime) -> T. **HTTP:** GET /v1/dppsByIdAndDate/{dppId}?date={UTC-instant}&representation=full.

| Parameters and request | Definition |
| --- | --- |
| dppId path | Required non-blank str; percent-encoded. |
| date query | Required timezone-aware datetime; normalized to UTC Z (seconds, milliseconds, or microseconds as required), then percent-encoded. |
| body/response | No body; successful envelope needs non-null full JSON payload decoded to T. |

**Example route:** /v1/dpps/DPP-1?date=2026-06-29T10%3A00%3A00Z&representation=full. **Null/errors:** naive datetime or blank ID raises ValueError before I/O; null payload/codec failure is mapping failure; shared errors apply. **Limit:** use this public versioned route for new code. **Evidence:** repo.py:read_dpp_version_by_id_and_date and _instant; test_dpp_id_history_uses_versioned_path_and_ordered_query; test_history_timestamp_wire_is_canonical_utc_z.

### read_dpp_version_by_product_id_and_date

**Purpose:** legacy product-ID history compatibility. **Signature:** read_dpp_version_by_product_id_and_date(product_id: str, date: datetime) -> T. **HTTP:** GET /dppsByProductIdAndDate/{productId}?date={UTC-instant}.

| Parameters and request | Definition |
| --- | --- |
| productId/date | Required non-blank encoded product ID and timezone-aware UTC-normalized instant. |
| body/response | No body; successful envelope requires non-null full JSON payload decoded to T. |

~~~json
{"statusCode":"Success","payload":{"callerCodecOwned":"full DPP JSON"},"messages":null}
~~~

**Null/errors:** same pre-I/O and shared errors as DPP-ID history. **Limit:** deprecated unversioned compatibility route; new code uses read_dpp_version_by_id_and_date. **Evidence:** repo.py:read_dpp_version_by_product_id_and_date; test_product_id_history_is_retained_unversioned_compatibility.

### read_dpp_ids_by_product_ids

**Purpose:** look up DPP IDs for product IDs. **Signature:** read_dpp_ids_by_product_ids(product_ids: list[str], limit: int | None = None, cursor: str | None = None) -> ReadDppIdsResponse. **HTTP:** POST /v1/dppsByProductIds; no path/query.

**Request body:** one ReadDppIdsRequest JSON object.

| Request field | Type and null behavior |
| --- | --- |
| productIdentifiers | list[str] or null; emitted even when None. |
| limit | int or null; emitted even when None. |
| cursor | str or null; emitted even when None. |

~~~json
{"productIdentifiers":["GTIN-0001"],"limit":25,"cursor":null}
~~~

| Response field | Type and method requirement |
| --- | --- |
| dppIdentifiers | list[str] or null in DTO; required non-null by this method. |
| nextCursor | str or null; may be null. |

~~~json
{"statusCode":"Success","payload":{"dppIdentifiers":["DPP-1"],"nextCursor":null},"messages":null}
~~~

**Errors/limit:** missing payload/dppIdentifiers is mapping failure; shared errors apply. The SDK forwards pagination values but does not validate product-ID syntax or provide a pagination iterator. **Evidence:** repo.py:read_dpp_ids_by_product_ids; payloads.py:ReadDppIdsRequest/ReadDppIdsResponse; test_read_dpp_ids; test_repository_dtos_preserve_nulls_defaults_and_unknown_field_policy.

### update_dpp_by_id

**Purpose:** send a partial JSON value and return a typed full passport. **Signature:** update_dpp_by_id(dpp_id: str, partial_dpp: Any) -> T. **HTTP:** PATCH /v1/dpps/{dppId}.

| Parameters and request | Definition |
| --- | --- |
| dppId path | Required non-blank str; percent-encoded. |
| body | Direct json.dumps(partial_dpp, allow_nan=False); None emits null. |
| success response | Successful envelope with non-null full JSON payload decoded to T. |

~~~json
{"characteristics":{"productName":"ErgoChair Pro"}}
~~~

**Example response:** {"statusCode":"Success","payload":{"callerCodecOwned":"full DPP JSON"},"messages":null}. **Null/errors:** NaN, infinity, sets, and non-JSON values raise DppMappingClientError before I/O; null response/codec failure is mapping failure; shared errors apply. **Limit:** direct JSON forwarding, not complete RFC 7396 merge-patch behavior. **Evidence:** repo.py:update_dpp_by_id and _serialize_partial_update; test_partial_updates_reject_unmappable_json_before_transport; test_partial_patch_decodes_response_without_whole_model_validation.

### read_data_element

**Purpose:** retrieve one raw selected JSON value. **Signature:** read_data_element(dpp_id: str, element_path: str) -> Any. **HTTP:** GET /v1/dpps/{dppId}/elements/{elementPath}.

| Parameters and request | Definition |
| --- | --- |
| dppId/elementPath | Required non-blank str values; each percent-encoded as one path segment. |
| body/response | No body; successful envelope requires non-null raw JSON payload returned unchanged. |

~~~json
{"statusCode":"Success","payload":"ErgoChair","messages":null}
~~~

**Null/errors:** blank inputs fail before I/O; null payload is mapping failure; shared errors apply. **Limit:** the client sends the path but does not evaluate JSONPath or implement complete RFC 9535 behavior. **Evidence:** repo.py:read_data_element; test_read_data_element_returns_the_raw_selected_json_value.

### update_data_element

**Purpose:** replace one selected raw JSON value. **Signature:** update_data_element(dpp_id: str, element_path: str, payload: Any) -> Any. **HTTP:** PATCH /v1/dpps/{dppId}/elements/{elementPath}.

| Parameters and request | Definition |
| --- | --- |
| paths | Required non-blank dppId and elementPath; both percent-encoded. |
| body | Direct strict JSON value; None emits null; not an UpdateDataElementRequest wrapper. |
| response | Successful envelope with required non-null raw JSON value returned unchanged. |

~~~json
"Updated element value"
~~~

~~~json
{"statusCode":"Success","payload":"Updated element value","messages":null}
~~~

**Null/errors:** non-representable/non-finite request data is mapping failure before I/O; null payload is mapping failure; shared errors apply. UpdateDataElementRequest(payload=...) remains importable only for compatibility. **Limit:** no local JSONPath evaluation/complete RFC 9535 support. **Evidence:** repo.py:update_data_element; test_update_data_element_sends_direct_payload; test_compatibility_element_dto_cannot_change_canonical_direct_body.

### delete_dpp_by_id

**Purpose:** delete one DPP. **Signature:** delete_dpp_by_id(dpp_id: str) -> DeleteDppResponse. **HTTP:** DELETE /v1/dpps/{dppId}.

| Parameters and response | Definition |
| --- | --- |
| dppId/body | Required non-blank encoded path; no request body. |
| statusCode | DppStatusCode or null, copied to DeleteDppResponse. |
| messages | list[DppApiMessage] or null, copied to DeleteDppResponse. |
| payload | Not required; a successful SuccessNoContent response may omit it or use null. |

~~~json
{"statusCode":"SuccessNoContent","payload":null,"messages":null}
~~~

**Errors/limit:** shared HTTP/API/network/mapping errors apply before the DTO is returned. The result contains envelope status/messages only. **Evidence:** repo.py:delete_dpp_by_id; payloads.py:DeleteDppResponse; test_delete_returns_status.

## Registry operation reference

### health_check

**Purpose:** registry reachability. **Signature:** health_check() -> bool. **HTTP:** GET /health; no parameters/body and Accept only. **Success/response:** bare health body is ignored; 2xx returns True, non-2xx/timeout/transport returns False. **Null/errors:** not applicable. **Limit:** no registration guarantee. **Evidence:** registry.py:DppRegistryClient.health_check; _http.py:probe_health; `tests/test_python_only_extensions.py:test_health_helpers_return_reachability_without_raising`.

### post_new_dpp_to_registry

**Purpose:** register passport metadata. **Signature:** post_new_dpp_to_registry(request: RegisterDppRequest) -> RegisterDppResponse. **HTTP:** POST /v1/registerDPP; no path/query.

**Request body:** one RegisterDppRequest JSON object.

| Request field | Type, alias, and null behavior |
| --- | --- |
| uniqueProductIdentifier | str or null; accepts input alias productIdentifier; emitted under the current name. |
| digitalProductPassportId | str or null; accepts dppIdentifier; emitted under the current name. |
| uniqueEconomicOperatorIdentifier | str or null; accepts operatorIdentifier; emitted under the current name. |
| dppApiEndpoint | str or null; accepts repoUrl; emitted under the current name. |

~~~json
{"uniqueProductIdentifier":"GTIN-0001","digitalProductPassportId":"DPP-1","uniqueEconomicOperatorIdentifier":"operator-123","dppApiEndpoint":"https://repo.example.com"}
~~~

The request object itself cannot be None; null/unserializable request maps to DppMappingClientError before I/O. DTO fields may be null and are emitted as null.

| Response field | Type and method requirement |
| --- | --- |
| registrationId | str or null in RegisterDppResponse, but required non-blank by this client method; registryIdentifier is its input alias. |

~~~json
{"statusCode":"SuccessCreated","payload":{"registrationId":"REG-1"},"messages":null}
~~~

**Errors/limit:** malformed payload or blank/missing registrationId is mapping failure; shared errors apply. There is no registry read-back, delete, cleanup, backup-operator, or internal-route operation. **Evidence:** registry.py:post_new_dpp_to_registry; payloads.py:RegisterDppRequest/RegisterDppResponse; test_registry_register_uses_canonical_wire_contract; test_registry_payload_canonical_keys_and_legacy_input_aliases.

## Examples and limitations

Use DTOs without the supplied clients only when your application owns HTTP transport:

~~~python
from dpp_sdk.clients import ReadDppIdsRequest, ReadDppIdsResponse

outgoing_json = ReadDppIdsRequest(productIdentifiers=["GTIN-0001"], limit=25).model_dump_json()
incoming_json = '{"dppIdentifiers":["DPP-1"],"nextCursor":null}'
assert ReadDppIdsResponse.model_validate_json(incoming_json).dppIdentifiers == ["DPP-1"]
~~~

Service-specific status behavior belongs to the optional [Java-services demo](../../../examples/java-services-demo/README.md), not to this generic client contract. Compression, partial update, and element-path limitations are stated with their operations above.

## Focused client checks

**Purpose:** run deterministic controlled-HTTP client checks. **Run from:** repository root.
**Prerequisites:** the checkout development environment. [RELEASING.md](../../../RELEASING.md) owns
installation, full validation, builds, archive inspection, and cleanup.

### PowerShell

```powershell
python -m pytest tests/test_clients.py tests/test_end_to_end.py
```

### Linux/macOS

```bash
python -m pytest tests/test_clients.py tests/test_end_to_end.py
```

**Expected result:** controlled client and end-to-end SDK tests pass without a live service.
**Cleanup:** none.

## Related documents and next steps

Use [SDK usage](../../../docs/usage.md) for a first integration, the [model guide](../../../docs/model-guide.md) for complete DPP fields, the [validation guide](../../../docs/validation-guide.md) for codec/validation stages, and [RELEASING.md](../../../RELEASING.md) for development and release commands.
