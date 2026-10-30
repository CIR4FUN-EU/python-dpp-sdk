# HTTP clients guide

![HTTP client request flow](architecture/python-client-request-flow.svg)

The repository and registry clients send and receive plain JSON. They don't build, check, or
convert passport models; your application does that (for example with `Dpp4FunJsonCodec`).
Create a client with the service's base URL. Optionally pass your own `httpx.Client` with
`client=`.

```python
from dpp_sdk.clients import DppRepoClient, DppRepresentation

with DppRepoClient("https://repo.example.com") as repo:
    created = repo.create_dpp(
        {
            "digitalProductPassportId": "urn:example:dpp:1",
            "uniqueProductIdentifier": "urn:example:product:1",
            "granularity": "model",
            "dppSchemaVersion": "1.0",
            "dppStatus": "active",
            "lastUpdated": "2026-10-16T00:00:00Z",
            "economicOperatorId": "urn:example:operator:1",
            "contentSpecificationIds": [],
            "elements": [
                {
                    "elementId": "nameplate",
                    "objectType": "DataElementCollection",
                    "elements": [
                        {
                            "elementId": "manufacturerName",
                            "objectType": "SingleValuedDataElement",
                            "value": "Example Furniture",
                            "valueDataType": "xsd:string",
                        }
                    ],
                }
            ],
        },
        DppRepresentation.FULL,
    )
    if created.digital_product_passport_id is None:
        raise RuntimeError("repository did not return a passport ID")
    try:
        result = repo.read_dpp_by_id(created.digital_product_passport_id, DppRepresentation.FULL)
        passport_json = result.payload
    finally:
        repo.delete_dpp_by_id(created.digital_product_passport_id)
```

Both clients are synchronous. Use them in a `with` block or call `close()`. This closes only a
client the SDK created itself; an `httpx.Client` you passed with `client=` remains caller owned,
so close it yourself. Default timeouts: 15 seconds per request, 5 seconds to connect. The base URL
must be an absolute `http://` or `https://` URL with a host and no query or fragment.
Requests send `Accept: application/json`, and `Content-Type: application/json` when they have a
body.

## Public operations

Repository reads and updates return `DppApiResponse`. Create returns `CreateDppResponse`, delete
returns `DeleteDppResponse`, and batch identifier lookup returns `ReadDppIdsResponse`. Registry
registration returns `RegisterDppResponse`. These wrappers expose Python `snake_case` attributes
while retaining the canonical JSON aliases.

| Public method | HTTP operation and payload | Result |
| --- | --- | --- |
| `create_dpp(dpp, representation=COMPRESSED)` | `POST /v1/dpps`; JSON-compatible DPP value | `CreateDppResponse` |
| `read_dpp_by_id(dpp_id, representation=COMPRESSED)` | `GET /v1/dpps/{dpp_id}` | `DppApiResponse` |
| `read_dpp_by_product_id(product_id, representation=COMPRESSED)` | `GET /v1/dppsByProductId/{product_id}` | `DppApiResponse` |
| `read_dpp_version_by_id_and_date(dpp_id, date, representation=COMPRESSED)` | `GET /v1/dppsByIdAndDate/{dpp_id}?date=...`; `date` must be timezone-aware | `DppApiResponse` |
| `read_dpp_ids_by_product_ids(product_ids, limit=None, cursor=None)` | `POST /v1/dppsByProductIds`; `ReadDppIdsRequest` JSON | `ReadDppIdsResponse` |
| `update_dpp_by_id(dpp_id, partial_dpp, representation=COMPRESSED)` | `PATCH /v1/dpps/{dpp_id}`; forwards the supplied JSON object | `DppApiResponse` |
| `delete_dpp_by_id(dpp_id)` | `DELETE /v1/dpps/{dpp_id}` | `DeleteDppResponse` |
| `read_data_element(dpp_id, element_id_path, representation=COMPRESSED)` | `GET /v1/dpps/{dpp_id}/elements/{element_id_path}` | `DppApiResponse` |
| `update_data_element(dpp_id, element_id_path, data_element, representation=COMPRESSED)` | `PATCH /v1/dpps/{dpp_id}/elements/{element_id_path}`; JSON DataElement value | `DppApiResponse` |
| `post_new_dpp_to_registry(request)` | `POST /v1/registerDPP`; `RegisterDppRequest` or JSON-compatible mapping | `RegisterDppResponse` |

`COMPRESSED` is the default. Pass `DppRepresentation.FULL` when you want to decode the result into
a typed passport; see [Representation and wire behavior](#representation-and-wire-behavior).

## Envelopes and errors

Every response has the JSON keys `statusCode`, `payload`, and `message`. In Python:

- `status_code`: a `DppStatusCode`, or `None`.
- `payload`: any JSON value. It may be missing where the API allows it. Create and registration
  identifiers are optional. Batch lookup requires `dppIdentifiers`, and element calls require a
  non-null payload.
- `message`: an optional list of `DppApiMessage`. Each one has `message_type` and `text`
  (required, blank text allowed) and optional `code`, `correlation_id`, and `timestamp`.

| HTTP response | Client behavior |
| --- | --- |
| 2xx with `Success`, `SuccessCreated`, or `SuccessAccepted` | Return the mapped operation response. |
| Repository 204 | Return `SuccessNoContent` without a payload. |
| 2xx with an API error `statusCode` | Raise `DppApiClientError`. |
| Non-2xx with a usable API error envelope | Raise `DppApiClientError` with HTTP status and messages. |
| Non-2xx without a usable API error envelope | Raise `DppHttpClientError` with HTTP status and raw body. |

| Exception | Meaning |
| --- | --- |
| `DppNetworkClientError` | HTTPX connection, transport, or timeout failure |
| `DppHttpClientError` | Non-2xx response without a usable error envelope |
| `DppApiClientError` | Non-success API status, on either a 2xx or structured non-2xx response |
| `DppMappingClientError` | JSON serialization, malformed envelope, or missing required operation payload |

Unknown fields in a response are ignored. Serialization errors are raised before the request is
sent.

`DppStatusCode` also recognizes `ClientErrorBadRequest`, `ClientNotAuthorized`, `ClientForbidden`,
`ClientMethodNotAllowed`, `ClientErrorResourceNotFound`, `ClientResourceConflict`,
`ServerNotImplemented`, `ServerInternalError`, and `ServerErrorBadGateway`. These are API envelope
values, not a promise that a service always chooses a particular numeric HTTP code.

## Representation and wire behavior

- `DppRepresentation.COMPRESSED` (the default) adds no query parameter. `DppRepresentation.FULL`
  sends `?representation=full`; the history route appends it after `date`.
- Request bodies are serialized from JSON-compatible Python values; non-finite numbers are
  rejected before the request is sent. The response `payload` is returned as plain JSON, without
  decoding into a model.
- Passport IDs and element paths are percent-encoded as path segments.
- A history `date` must be timezone-aware; the client converts it to UTC.
- The client forwards PATCH bodies unchanged. It does not implement JSON Merge Patch or validate
  element paths; how a PATCH is applied is up to the service.

## Pagination and registry metadata

`read_dpp_ids_by_product_ids(product_ids, limit=None, cursor=None)` sends
`{"productIdentifiers": [...], "limit": null, "cursor": null}` when optional arguments are
omitted. Its `ReadDppIdsResponse` requires `dppIdentifiers` and may contain `nextCursor`. Pass that
cursor on a later call to request the next page; the client has no iterator or automatic traversal.

`RegisterDppRequest` contains optional `unique_product_identifier`,
`digital_product_passport_id`, `unique_economic_operator_identifier`, and `dpp_api_endpoint` fields.
The request is registry metadata: it does not upload a passport. Registration may return an optional
`registration_id`; there is no public registry read-back or delete method in this Python client.

## Decode a response into a typed passport

The clients return plain JSON and the codecs read JSON strings, so convert between them with the
`json` module. Request `FULL`, because `from_json()` reads the FULL form:

```python
import json

from dpp_sdk import Dpp4FunJsonCodec
from dpp_sdk.clients import DppRepoClient, DppRepresentation
from dpp_sdk.dpp4fun import Nameplate

codec = Dpp4FunJsonCodec()
with DppRepoClient("https://repo.example.com") as repo:
    response = repo.read_dpp_by_id("urn:example:dpp:1", DppRepresentation.FULL)

passport = codec.from_json(json.dumps(response.payload))  # or from_json_and_validate()
nameplate = passport.typed_aspect(Nameplate)
```

For a COMPRESSED payload use `codec.from_compressed_json(json.dumps(response.payload))`; the DPP4Fun
profile restores the types. To send a typed passport, go the other way:
`repo.create_dpp(json.loads(codec.to_json(passport)), DppRepresentation.FULL)`.

The [full lifecycle example](../examples/consumer_lifecycle.py) builds, validates, creates, reads,
updates, reads history, registers, and cleans up a passport. There is no registry cleanup method,
so run it against a disposable service.

## Known limitations

- No authentication, retries, automatic pagination, or async client.
- No registry read-back or delete.
- No JSON Merge Patch or JSONPath implementation; PATCH semantics belong to the service.
- No validation: validate passports with the model validators before sending them.
- Mock-service `/internal/...` routes are not client operations.

