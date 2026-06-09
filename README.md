# dpp-sdk (Python)

Python SDK for **Digital Product Passports (DPP)** — an idiomatic [Pydantic v2](https://docs.pydantic.dev)
port of the Java DPP SDK in the sibling repo `../dpp-sdk-platform`.

## Install

```bash
pip install dpp-sdk
```

Requires Python 3.11+.

## Quickstart

```python
from dpp_sdk import Dpp4Fun, from_json, to_json, validate_dpp4fun

# Parse an incoming passport (accepts both flat and nested JSON shapes)
dpp = from_json(raw_json)

# Validate against the DPP rule set (raises on violations)
validate_dpp4fun(dpp)

# Serialize back to the flattened wire JSON
payload = to_json(dpp)
```

The `httpx`-based HTTP clients for the DPP repository and registry live in `dpp_sdk.clients`:

```python
from dpp_sdk.clients import DppRepoClient, DppRegistryClient
```

See [`docs/PORTING_PLAN.md`](docs/PORTING_PLAN.md) for design notes and
[`docs/RELEASING.md`](docs/RELEASING.md) for how releases are cut.

## Scope

| Package | Purpose | Java source ported from |
|---|---|---|
| `dpp_sdk.core` | Reusable core DPP model, validation, JSON transport | `dpp-datamodel/dpp-core` |
| `dpp_sdk.dpp4fun` | Furniture-specific DPP aggregate | `dpp-datamodel/dpp4fun` |
| `dpp_sdk.clients` | HTTP clients for the DPP repository & registry APIs | `dpp-sdk-clients` |

The Spring Boot mock services in `../dpp-sdk-platform/dpp-sdk-demo` are **not** ported; they are
reused as a conformance oracle for client tests.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest        # tests
mypy          # type check (strict)
ruff check .  # lint
```

## Layout

```
src/dpp_sdk/
  core/        # core model + validation
  dpp4fun/     # furniture aggregate, validation, JSON transport
  clients/     # repo + registry HTTP clients
tests/         # pytest suite
docs/          # PORTING_PLAN.md, RELEASING.md
```
