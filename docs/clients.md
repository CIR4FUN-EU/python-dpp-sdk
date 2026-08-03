# Clients

## Scope

`dpp_sdk.clients` contains synchronous HTTPX consumers of public DPP repository and registry API
contracts. The package does not implement either service. Pass application endpoints explicitly;
the `for_local_mock()` helpers are only local-development conveniences.

The editable flow diagram is [python-client-flow.mmd](diagrams/python-client-flow.mmd).

## Repository client

Construct `DppRepoClient[T]` with a base URL, a full-payload codec, and a semantic validator. The
client validates before `create_dpp()`, serializes with the supplied codec, and maps full DPP
responses with that same codec.

| Public operation | Method | Result |
| --- | --- | --- |
| Create | `create_dpp(dpp)` | `CreateDppResponse` |
| Read by DPP ID | `read_dpp_by_id(dpp_id)` | `T` |
| Read by product ID | `read_dpp_by_product_id(product_id)` | `T` |
| Read compressed DPP | `read_compressed_dpp_by_id(dpp_id)` | untyped compressed payload |
| Historical read by DPP ID | `read_dpp_version_by_id_and_date(dpp_id, date)` | `T` |
| Bulk product-ID lookup | `read_dpp_ids_by_product_ids(product_ids, limit, cursor)` | `ReadDppIdsResponse` |
| Full update | `update_dpp_by_id(dpp_id, partial_dpp)` | `T` |
| Fine-grained read | `read_data_element(dpp_id, element_path)` | payload value |
| Fine-grained update | `update_data_element(dpp_id, element_path, payload)` | payload value |
| Delete | `delete_dpp_by_id(dpp_id)` | `DeleteDppResponse` |

`read_dpp_version_by_product_id_and_date()` remains a deprecated compatibility route. It is not
the preferred history operation for new integrations.

Full reads request `representation=full`; compressed reads request `representation=compressed`.
Fine-grained update sends the supplied value directly as the JSON request body, including `None` as
JSON `null`; it does not wrap that value in an extra object. Dynamic path segments are percent
encoded, and historical timestamps must be timezone-aware and are normalized to UTC with `Z`.

## Registry client

`DppRegistryClient` currently exposes:

| Public operation | Method | Result |
| --- | --- | --- |
| Health probe | `health_check()` | `bool` |
| Register a DPP | `post_new_dpp_to_registry(request)` | `RegisterDppResponse` |

Use `RegisterDppRequest` with canonical fields `uniqueProductIdentifier`,
`digitalProductPassportId`, `uniqueEconomicOperatorIdentifier`, and `dppApiEndpoint`.
`RegisterDppResponse.registrationId` is the successful registration identifier. Public registry
read-back, cleanup, and internal lifecycle operations are not part of this SDK surface.

## Errors

| Error family | Meaning |
| --- | --- |
| `DppValidationClientError` | Local DPP validation failed before a repository request. |
| `DppMappingClientError` | Request serialization or response mapping failed. |
| `DppNetworkClientError` | Transport or timeout failure. |
| `DppHttpClientError` | Non-2xx HTTP response. |
| `DppApiClientError` | API envelope reports a non-success status. |

All are subclasses of `DppClientError`. The distinction tells callers whether a request was
rejected locally, failed on the network, or received a service response.

## Resource ownership

Both clients can be context managers. A client constructed without an injected `httpx.Client` owns
and closes its HTTP resource on `close()` or context exit. An injected client remains caller-owned.

```python
with DppRegistryClient("https://registry.example.com") as registry:
    assert registry.health_check()
```

## Interoperability evidence

The [Java-services demo](../examples/java-services-demo/README.md) is the optional external
consumer that exercises these methods against disposable published Java images. It is not a
repository implementation and does not prove unsupported internal registry behavior. For typed
model and codec setup, see [SDK usage](usage.md).

Next: [Java-services demo](../examples/java-services-demo/README.md) for the isolated public-client
interoperability workflow.
