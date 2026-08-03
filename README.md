# dpp-sdk (Python)

`dpp-sdk` is a Python 3.11+ consumer SDK for Digital Product Passports (DPPs). It provides
immutable Pydantic models, explicit semantic validation, DPP4Fun JSON codecs, and synchronous
clients for public DPP repository and registry APIs.

It is a reusable client library. It does not operate a repository or registry, and it contains no
backend, persistence, Docker, Spring, EDC, or dataspace implementation. The Java-services demo is
an isolated external consumer, not part of `dpp_sdk`.

## Architecture at a glance

```text
dpp_sdk.core       models, identifiers, shared errors, semantic validation
       ^
       |----------------------------|
dpp_sdk.dpp4fun                    dpp_sdk.clients
furniture aggregate and codec      synchronous repository and registry clients
```

`dpp_sdk.core` is the reusable dependency base. `dpp_sdk.dpp4fun` and `dpp_sdk.clients` consume
core contracts; consumer applications compose those modules. The Java-services demo remains an
external consumer and does not belong to the import package.

## Standards alignment

- **EN 18222:2026:** The SDK implements selected public DPP repository and registry API shapes,
  alongside the project DPP4Fun model, validation, and JSON transport contracts. This is not a formal compliance implementation.
  It makes no certification, legal-conformity statement, or production-readiness claim.
- **Repository lifecycle operations:** The public repository client supports create, read, full and
  fine-grained update, historical read, and delete operations. These operations align with the
  lifecycle-management scope considered by EN 18222, but the Python SDK does not implement a
  repository, persistence layer, or lifecycle-event model.

## Known standards limitations

- **Compression:** The compressed representation is project-defined. The client returns it as an
  untyped payload and does not claim a formally validated EN representation.
- **Partial update and element paths:** The SDK exposes the documented repository update routes,
  but it does not claim a complete generic implementation of RFC 7396 JSON Merge Patch or a
  complete implementation of RFC 9535 JSONPath. Full updates use the repository's public partial-
  DPP contract; fine-grained reads and updates send the supplied path and direct JSON value to the
  service without evaluating path expressions locally.
- **Lifecycle events:** The SDK does not record lifecycle events or provide a lifecycle-event
  history representation. Those Java service/model extensions are outside the Python SDK's public
  surface.

## Install

PowerShell:

```powershell
python -m pip install dpp-sdk
```

Linux/macOS:

```bash
python -m pip install dpp-sdk
```

## Shortest useful path

Parse a DPP4Fun payload, run its semantic rules, and serialize its interoperable JSON form:

```python
from dpp_sdk import from_json, to_json, validate_dpp4fun


def parse_validate_and_serialize(raw_json: str) -> str:
    dpp = from_json(raw_json)
    validate_dpp4fun(dpp)
    return to_json(dpp)
```

`from_json()` performs structural mapping. Call `validate_dpp4fun()` before relying on the
semantic rules or sending a model to a service.

## Contract notes

Semantic validation is fail-fast. Models use immutable tuples for contracted collections; use
`with_updates()` for a structurally revalidated immutable replacement. The client guide owns the
full operation reference, including `read_compressed_dpp_by_id`, the canonical
`read_dpp_version_by_id_and_date`, and the legacy compatibility only product-history route.

Repository creation uses `POST /v1/dpps`; registry registration uses `POST /v1/registerDPP`. A
registration request identifies its repository with
`dppApiEndpoint="https://repo.example.com"`. `UpdateDataElementRequest` remains importable for
compatibility, while the canonical fine-grained update sends its value directly. Mapping failures
in client code use `DppMappingClientError`. An injected HTTPX client remains caller-owned.

## Guides

Start with the end-to-end guide when you need more than the shortest path:

1. [SDK usage](docs/usage.md) — construction, validation, codecs, updates, and client ownership.

For module-specific API references, examples, boundaries, and contributor commands, see:

- [Core module](src/dpp_sdk/core/README.md)
- [DPP4Fun module](src/dpp_sdk/dpp4fun/README.md)
- [Clients module](src/dpp_sdk/clients/README.md)

For package release work, see [RELEASING.md](RELEASING.md).

## Java-services demo

[`examples/java-services-demo`](examples/java-services-demo/README.md) installs separately and
uses disposable published Java services to exercise the public Python clients. Its maintained
target is Java repository and registry image version `0.5.0`, with immutable pinned image
references as the reproducible default. Version `0.4.0` is an optional legacy check and is not a
maintained Python SDK compatibility guarantee.
