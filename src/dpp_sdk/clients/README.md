# DPP SDK clients module

## Purpose and model independence

`dpp_sdk.clients` contains synchronous HTTPX consumers for public DPP repository and registry API
contracts. `DppRepoClient[T]` is model-independent: the application supplies a full-payload
`DppCodec[T]` and a semantic `DppValidator[T]`. `DppRegistryClient` uses public registration DTOs
and does not transfer a complete DPP.

The module does not implement a repository or registry service, persistence, authentication,
retries, async clients, internal registry APIs, lifecycle-event recording, or Docker runtime.

## Architecture at a glance

```text
Application DPP ── codec + validator ──> DppRepoClient[T] ──> public repository API
Application metadata ── RegisterDppRequest ──> DppRegistryClient ──> public registry API
```

The caller supplies endpoints explicitly. `for_local_mock()` is a local-development convenience,
not a production service configuration mechanism.

## Public surface

### Repository client

| Operation | Method | Result |
| --- | --- | --- |
| Health probe | `health_check()` | `bool` |
| Create | `create_dpp(dpp)` | `CreateDppResponse` |
| Read by DPP ID | `read_dpp_by_id(dpp_id)` | `T` |
| Read by product ID | `read_dpp_by_product_id(product_id)` | `T` |
| Read compressed DPP | `read_compressed_dpp_by_id(dpp_id)` | untyped payload |
| Historical read | `read_dpp_version_by_id_and_date(dpp_id, date)` | `T` |
| Bulk product-ID lookup | `read_dpp_ids_by_product_ids(product_ids, limit, cursor)` | `ReadDppIdsResponse` |
| Full update | `update_dpp_by_id(dpp_id, partial_dpp)` | `T` |
| Fine-grained read | `read_data_element(dpp_id, element_path)` | payload value |
| Fine-grained update | `update_data_element(dpp_id, element_path, payload)` | payload value |
| Delete | `delete_dpp_by_id(dpp_id)` | `DeleteDppResponse` |

`read_dpp_version_by_product_id_and_date()` remains a deprecated compatibility route. New code
should use the DPP-ID history route.

### Registry client and payloads

| Operation | Method | Result |
| --- | --- | --- |
| Health probe | `health_check()` | `bool` |
| Register a DPP | `post_new_dpp_to_registry(request)` | `RegisterDppResponse` |

Use `RegisterDppRequest` with `uniqueProductIdentifier`, `digitalProductPassportId`,
`uniqueEconomicOperatorIdentifier`, and `dppApiEndpoint`. Public registry read-back, cleanup, and
internal lifecycle operations are not part of this module.

## Client setup and controlled example

The repository client requires a base URL, codec, and validator. The following no-network example
uses an injected controlled transport to prove the health call shape; it is not evidence of live
Java service interoperability.

```python
import httpx

from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppRepoClient


def handle(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"
    assert request.url.path == "/health"
    return httpx.Response(200, request=request)


with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
    with DppRepoClient(
        "https://repo.example.com",
        codec=Dpp4FunJsonCodec(),
        validator=validate_dpp4fun,
        client=http_client,
    ) as repository:
        assert repository.health_check()
```

The injected HTTPX client remains caller-owned. A client created by the SDK is closed by `close()`
or context-manager exit.

## Wire behavior and errors

Full reads request `representation=full`; compressed reads request `representation=compressed` and
return an untyped payload. Historical timestamps must be timezone-aware; the client normalizes them
to UTC with `Z`. Dynamic path segments are percent encoded.

Fine-grained update sends the supplied payload itself as the JSON request body, including `None` as
JSON `null`; it does not wrap the value. The client transmits the provided element path but does not
interpret or validate it as a complete JSONPath implementation.

Partial and fine-grained update bodies use strict JSON. Finite numbers, Unicode text, objects,
lists, and `None` retain their ordinary JSON representation. `NaN`, `Infinity`, `-Infinity`, and
values JSON cannot represent raise `DppMappingClientError` before any request is sent; the original
`ValueError` or `TypeError` remains the exception cause.

| Error family | Meaning |
| --- | --- |
| `DppValidationClientError` | Local DPP validation failed before create is sent. |
| `DppMappingClientError` | Request serialization or response mapping failed. |
| `DppNetworkClientError` | Transport or timeout failure. |
| `DppHttpClientError` | Non-2xx HTTP response. |
| `DppApiClientError` | API envelope reports non-success status. |

All are subclasses of `DppClientError`. Partial and fine-grained updates are not semantically
validated by the client because they can be incomplete DPP fragments; the target service owns
validation of the resulting aggregate.

## Build and test locally

This module is part of the single `dpp-sdk` distribution; it is not a separately buildable or
published package. Run commands from the repository root.

PowerShell:

```powershell
python -m pip install -e ".[dev,release]"
python -m build
python -m pytest tests/test_clients.py tests/test_end_to_end.py
```

Linux/macOS:

```bash
python -m pip install -e ".[dev,release]"
python -m build
python -m pytest tests/test_clients.py tests/test_end_to_end.py
```

`python -m build` builds the complete SDK distribution. The controlled HTTP tests are deterministic;
live Java-image interoperability belongs to the separately installed
[Java-services demo](../../../examples/java-services-demo/README.md).

## Boundaries and limitations

- The SDK is a consumer of documented public service APIs; it does not provide service-side behavior.
- Compression is project-defined and is not decoded as `T` by the repository client.
- The module does not claim complete RFC 7396 JSON Merge Patch or RFC 9535 JSONPath support.
- No formal standards compliance, certification, legal conformity, or production-readiness claim is
  made.

Next: [Java-services demo](../../../examples/java-services-demo/README.md) for disposable-image
interoperability, or [SDK usage](../../../docs/usage.md) for the end-to-end consumer tutorial.
