# dpp-sdk (Python)

`dpp-sdk` helps Python applications work with Digital Product Passports (DPPs). You can use it
to describe a passport, check it, turn it into JSON, and call a DPP repository or registry API.

It is a client library, not a service. It does not run a repository or registry, store data, or
provide Docker, Spring, EDC, or dataspace features. The Java-services demo is a separate optional
consumer of this SDK.

## Start here

Choose the smallest part that matches your job:

| If you want to… | Start with… |
| --- | --- |
| describe reusable passport details | [Core module](src/dpp_sdk/core/README.md) |
| work with furniture passports | [DPP4Fun module](src/dpp_sdk/dpp4fun/README.md) |
| call a repository or registry API | [Clients module](src/dpp_sdk/clients/README.md) |
| see a complete consumer walkthrough | [SDK usage](docs/usage.md) |
| understand package boundaries | [SDK overview](docs/overview.md) |
| look up model fields and JSON/null semantics | [Model guide](docs/model-guide.md) |
| look up semantic validation rules | [Validation rules](docs/validation-rules.md) |
| try disposable Java services locally | [Java-services demo](examples/java-services-demo/README.md) |
| prepare a package release | [Release guide](RELEASING.md) |
| review changes or licensing | [Changelog](CHANGELOG.md) · [License](LICENSE) |

## Architecture at a glance

![Python SDK architecture](docs/architecture/python-sdk-overview.svg)

*Diagram: your application can use core models directly or through DPP4Fun. It can also use the
generic HTTP clients; the separate demo uses those same public clients against disposable Java
services.*

`dpp_sdk.dpp4fun` builds on `dpp_sdk.core`. `dpp_sdk.clients` is separate and generic: your
application tells it how to check and convert its own passport model. The clients do not depend on
the concrete core or DPP4Fun packages.

## Prerequisites

- **All SDK users:** Python 3.11 or newer.
- **Only for the optional live Java-services demo:** Docker Engine with Compose v2, Docker Buildx
  for the demo's image-identity check, and access to the public GHCR image references.

You do not need Docker, Compose, Buildx, or GHCR access to install the SDK, use its models, or run
the SDK-only demo checks.

## Install

**Purpose:** install the published SDK for an application. **Run from:** any directory; these
commands are directory-independent because pip downloads a named published distribution rather
than reading this checkout. **Prerequisites:** Python 3.11 or newer on `PATH` and access to the
selected package index.

Choose the source deliberately:

| Need | Install choice | Why |
| --- | --- | --- |
| ordinary application use | latest published `dpp-sdk` | uses the newest released distribution; no checkout is required |
| repeatable deployment or compatibility testing | an exact published version such as `dpp-sdk==0.2.1` | prevents a later release from changing the installed SDK |
| updates within one released minor line | a compatible version range such as `dpp-sdk~=0.2.1` | accepts compatible `0.2.x` fixes but not `0.3.0` |
| contribution, an unreleased fix, or reproducing checkout state | install this local checkout | uses the source currently in this repository; it is not a substitute for a released package in production |

Release tags are named `v<major>.<minor>.<patch>` (for example, `v0.2.1`), while pip version
selectors omit the `v` (for example, `dpp-sdk==0.2.1`).

### PowerShell

```powershell
python -m pip install dpp-sdk
```

### Linux/macOS

```bash
python -m pip install dpp-sdk
```

### Install a selected published release

Use an exact version when deployment must be reproducible. Use `~=` only when your application
has tested the compatible release line and can accept later patch releases.

#### PowerShell

```powershell
python -m pip install "dpp-sdk==0.2.1"
python -m pip install "dpp-sdk~=0.2.1"
```

#### Linux/macOS

```bash
python -m pip install "dpp-sdk==0.2.1"
python -m pip install "dpp-sdk~=0.2.1"
```

### Install this local checkout

Use this only when you need the un-released source in this checkout, are contributing, or are
reproducing a source-state issue. Create the repository-local `.venv` once when it is absent; it is
local developer state and must not be committed.

#### Create the development environment

**Purpose:** create an isolated checkout environment with development and release tools.
**Run from:** the Python repository root, the directory containing `pyproject.toml`.
**Prerequisites:** Python 3.11 or newer on `PATH`.

##### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,release]"
```

##### Linux/macOS

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev,release]"
```

**Expected result:** `.venv` contains an isolated editable SDK install plus the configured test,
lint, type-check, build, and package-check tools. **Cleanup:** remove `.venv` only when you no
longer need this checkout environment.

#### PowerShell

```powershell
.\.venv\Scripts\python.exe -m pip install .
```

#### Linux/macOS

```bash
.venv/bin/python -m pip install .
```

`dpp-sdk` is the single package that contains the core, DPP4Fun, clients, and public payload
models. The separately installed `dpp-sdk-java-services-demo` package is reference/demo code, not
a dependency that ordinary SDK users need.

**Expected result:** the same interpreter imports the intended SDK:

```powershell
.\.venv\Scripts\python.exe -c "import dpp_sdk; print(dpp_sdk.__version__)"
```

```bash
.venv/bin/python -c "import dpp_sdk; print(dpp_sdk.__version__)"
```

**Cleanup:** none.

## First use from this checkout

All local commands in this section run from the repository root, the directory containing
`pyproject.toml`.

1. Choose a published install above, or create `.venv` and install this checkout.
2. Run the import probe above, then use the small SDK example below.
3. Run the SDK-only educational walkthrough after following the isolated-wheel setup in the
   [Java-services demo guide](examples/java-services-demo/README.md#step-6-run-the-sdk-only-educational-walkthrough):
   `./.java-services-demo-venv/Scripts/python.exe -m dpp_java_services_demo sdk` on PowerShell, or
   `./.java-services-demo-venv/bin/python -m dpp_java_services_demo sdk` on Linux/macOS. Use
   `--summary` for compact verification or `--json` for machine-readable evidence.
4. Run SDK tests with the development interpreter; focused core, validation, client, and
   documentation commands are owned by the [release guide](RELEASING.md).
5. Only when you need live interoperability, follow the [Java-services demo guide]
   (examples/java-services-demo/README.md) to start a uniquely named disposable project, run
   `demo`, `full`, or `verify`, inspect its report/logs, and tear down only that project.

The demo guide owns its longer service commands and troubleshooting. Docker is never required for
the installation, SDK example, or SDK-only demo.

## A small useful example

Parse a furniture passport, check it, and turn it back into JSON:

```python
from dpp_sdk import from_json, to_json, validate_dpp4fun


def check_passport(raw_json: str) -> str:
    passport = from_json(raw_json)
    validate_dpp4fun(passport)
    return to_json(passport)
```

`from_json()` checks that the JSON has the right shape. `validate_dpp4fun()` checks the extra
business rules. Run validation before relying on a passport or sending it to a service.

## Store and read a passport

Once you have a valid `Dpp4Fun` value and a repository URL, the generic client can store and read
it. The same pattern works with your own model when you provide a codec and validator.

```python
from dpp_sdk import Dpp4Fun, Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppRepoClient


def store_and_read(dpp: Dpp4Fun, repository_url: str) -> Dpp4Fun:
    with DppRepoClient(
        repository_url,
        codec=Dpp4FunJsonCodec(),
        validator=validate_dpp4fun,
    ) as repository:
        created = repository.create_dpp(dpp)
        return repository.read_dpp_by_id(created.dppId)
```

For all operations, request and response payloads, errors, partial updates, and resource ownership,
see the [clients module guide](src/dpp_sdk/clients/README.md).

## Standards alignment

**EN 18222:2026:** The SDK implements selected public DPP repository and registry API shapes
alongside the project DPP4Fun model, validation, and JSON rules. It is not a formal compliance implementation. It also makes no certification, legal-conformity, or production-readiness claim.

Some API contracts were designed using confidential external technical specifications that cannot
be published here. This documentation describes only the behavior implemented by this project.

### What the SDK supports

- Create, read, update, read historical versions of, and delete repository passports.
- Register passport metadata with a registry.
- Read a compressed passport as an untyped JSON value when the service provides one.

## Known standards limitations

- The registry request has no backup-operator field or backup-operator operation.
- Compressed passports use a project-defined format. The SDK does not turn them into a typed
  `Dpp4Fun` value automatically.
- Partial updates and element paths are only partly implemented. The SDK sends the documented
  requests, but it does not provide a complete generic implementation of RFC 7396 JSON Merge Patch
  or a complete implementation of RFC 9535 JSONPath.
- The Python SDK does not record lifecycle events or keep a lifecycle-event history.
- Authentication, backup/recovery, retries, persistence, and other production operations are not
  provided.
- The SDK calls public `/v1/...` service routes. Java demo `/internal/...` routes are not Python
  client methods.
- No real EU registry integration, production security hardening, or production-operational
  guarantee is provided.

### Technical details

Repository creation uses `POST /v1/dpps`; registry registration uses `POST /v1/registerDPP`. A
registration request identifies its repository with `dppApiEndpoint="https://repo.example.com"`.
Full reads use a typed model; compressed and fine-grained reads return the JSON value supplied by
the service. The typed compressed-read method is `read_compressed_dpp_by_id()`.

`UpdateDataElementRequest` remains importable for compatibility, while the normal fine-grained
update sends its value directly. The client guide explains exact JSON field names, error types, and
supported paths.

`read_dpp_version_by_product_id_and_date()` remains a legacy compatibility only route. New code
should use `read_dpp_version_by_id_and_date()` with a DPP ID.

Semantic validation is fail-fast. Models use immutable tuples for contracted collections; use
`with_updates()` to make a checked replacement instead of changing a model in place. Mapping
failures in client code use `DppMappingClientError`; an HTTPX client you provide stays caller-owned.

## Optional Java-services demo

The [Java-services demo](examples/java-services-demo/README.md) uses disposable Java repository
and registry images to exercise the public Python clients. It is maintained against Java image
version `0.5.0` with pinned image references; version `0.4.0` is optional legacy evidence only.
Its guide separates an SDK-only walkthrough, a curated live demonstration, a broad full health
check, and strict verification; only strict verification makes package-provenance and image-identity
claims.

## Quick Java-service checks

**Run from:** the Python repository root. These are the shortest useful commands when you want to
exercise the Python SDK against the reusable Java repository and registry images. They do not need a
Java source checkout. For environment setup, alternate ports, demo commands, logs, stopping, and
permanent deletion, use the [Java-services demo guide](examples/java-services-demo/README.md).

### 1. Start one isolated Java-service project

```powershell
$project = "dpp-java-services-demo-$PID"
& .\examples\java-services-demo\manage-java-services.ps1 -Action Start -Project $project
```

### 2. Run Python unit and controlled tests only

**What this does:** runs the root Python suite while explicitly excluding marked live integration
tests. It does not need Docker or Java services.

```powershell
& .\.venv\Scripts\python.exe -m pytest .\tests -m "not integration"
```

### 3. Run complete Python-to-Java live tests

Run this only after the successful Start command above. These tests call the already-running Java
images through the public Python SDK clients; they do not start Docker themselves.

```powershell
& .\.venv\Scripts\python.exe -m pytest .\tests\test_integration_live.py --run-java-services
& .\.venv\Scripts\python.exe -m pytest -c .\examples\java-services-demo\pyproject.toml `
  .\examples\java-services-demo\tests --run-java-services
```

## Linux/macOS quick checks

Run these from the same repository root when PowerShell is not your shell. They use the same
reusable lifecycle script and service-test boundary as the PowerShell commands above.

```bash
project="dpp-java-services-demo-$$"
pwsh -File ./examples/java-services-demo/manage-java-services.ps1 -Action Start -Project "$project"

# Python unit and controlled tests only — no Docker or Java service calls.
.venv/bin/python -m pytest ./tests -m "not integration"

# Complete Python-to-Java live test suites; requires the successful Start command above.
.venv/bin/python -m pytest ./tests/test_integration_live.py --run-java-services
.venv/bin/python -m pytest -c ./examples/java-services-demo/pyproject.toml \
  ./examples/java-services-demo/tests --run-java-services
```

### Run the optional Java services from another location

**What this does:** starts an isolated repository-and-registry stack from pinned public images; it
does not need a Java source checkout. Copy the complete `examples/java-services-demo` directory
(the script needs its adjacent `compose.yaml` and `env/` profiles) wherever you want to run the
stack, then use PowerShell 7+ with a project name you own:

```powershell
pwsh -File .\java-services-demo\manage-java-services.ps1 -Action Start -Project my-dpp-demo
```

The script validates the Compose profile, pulls missing images, starts the project, and checks
both service health endpoints. The [demo guide](examples/java-services-demo/README.md) owns the
labelled status, logs, stop, deletion, and educational-demo commands.

When that optional stack is running, open `http://localhost:8080/` or
`http://localhost:8081/` in a browser for the Java service Swagger UI. Use `/health` for a simple
health check and `/v3/api-docs` for the service OpenAPI JSON. These are Java demo service endpoints,
not endpoints provided by the Python package.

## Documentation and next steps

For a first integration, follow the [SDK usage guide](docs/usage.md). Use the [SDK overview]
(docs/overview.md) to understand package boundaries, the [model guide](docs/model-guide.md) for
field/default/null behavior, the [validation guide](docs/validation-guide.md) and
[validation-rule reference](docs/validation-rules.md) for validation and codec behavior, and the
[clients guide](src/dpp_sdk/clients/README.md) for every public HTTP operation and payload. The
[release guide](RELEASING.md) owns development and release validation; the separate
[Java-services demo](examples/java-services-demo/README.md) owns its optional service lifecycle.
