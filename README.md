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

See the [SDK overview](docs/overview.md) for the public boundaries and dependency direction.

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

Read the guides in this order when you need more than the shortest path:

1. [SDK overview](docs/overview.md) — package boundaries and supported scope.
2. [SDK usage](docs/usage.md) — construction, validation, codecs, updates, and client ownership.
3. [Models and validation](docs/models-and-validation.md) — model families and rule ownership.
4. [Clients](docs/clients.md) — repository and registry operations, wire concerns, and errors.

For package release work, see [RELEASING.md](RELEASING.md).

## Java-services demo

[`examples/java-services-demo`](examples/java-services-demo/README.md) installs separately and
uses disposable published Java services to exercise the public Python clients. Its maintained
target is Java repository and registry image version `0.5.0`, with immutable pinned image
references as the reproducible default. Version `0.4.0` is an optional legacy check and is not a
maintained Python SDK compatibility guarantee.
