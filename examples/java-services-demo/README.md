# Python SDK Java-services demo

This directory is an isolated consumer of the published `dpp-sdk` package. It demonstrates the
public Python SDK and provides pull-only Compose infrastructure for the published Java DPP
repository and registry images. It does not add backend, persistence, Docker, demo-service, or
EDC responsibilities to `dpp_sdk`.

This foundation implements all SDK-local scenarios. Live repository and registry operations are
deliberately deferred to the next implementation phase; the `services`, `all`, and `verify` modes
report `NOT_IMPLEMENTED` and exit nonzero until that work is complete.

## Compatibility and image policy

The reproducible default is [`env/pinned.env`](env/pinned.env), whose tag-plus-digest references
are immutable. [`env/0.5.0.env`](env/0.5.0.env) is the maintained semantic-version profile. A
future live verification report must resolve and record both profiles' image identities and
compare them dynamically; historical digest equality is not assumed to remain true.

> The demo is maintained against Java repository and registry version 0.5.0 and the recorded
> immutable image digest. Version 0.4.0 is retained as an optional legacy compatibility target
> and is not part of the maintained compatibility guarantee.

[`env/0.4.0.env`](env/0.4.0.env) is informational and requires the explicit `--legacy` CLI flag.
Its eventual live outcome will use exactly `LEGACY_COMPATIBILITY_PASSED`,
`LEGACY_COMPATIBILITY_FAILED`, or `LEGACY_COMPATIBILITY_NOT_RUN`. A 0.4.0 failure is not a
current Python SDK defect, contract mismatch, release blocker, or reason to add a compatibility
shim.

## Prerequisites and installation

- Python 3.11 or newer.
- A built `dpp-sdk` 0.2.1 wheel.
- Docker with Compose v2 only for pulling or running the Java images.
- Access to the public GHCR image references in the selected profile.

Build the root SDK first:

```powershell
# From the Python SDK repository root
python -m build
Set-Location .\examples\java-services-demo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ..\..\dist\dpp_sdk-0.2.1-py3-none-any.whl ".[dev]"
```

```bash
# From the Python SDK repository root
python -m build
cd examples/java-services-demo
python -m venv .venv
./.venv/bin/python -m pip install ../../dist/dpp_sdk-0.2.1-py3-none-any.whl ".[dev]"
```

The nested project depends on `dpp-sdk==0.2.1` as an installed package. It never adds the root
`src` directory to its import path and is not separately published.

## SDK-only demonstration

The SDK mode requires no Docker:

```powershell
.\.venv\Scripts\python.exe -m dpp_java_services_demo sdk
.\.venv\Scripts\python.exe -m dpp_java_services_demo sdk --json
```

```bash
./.venv/bin/python -m dpp_java_services_demo sdk
./.venv/bin/python -m dpp_java_services_demo sdk --json
```

It runs SDK-01 through SDK-15: complete and minimal typed fixtures, identifiers, core and
Dpp4Fun semantic validation, flat/nested codec behavior, semantic round trips, immutable
updates, public errors, whitespace, numeric, null/root, aggregate, Bill of Materials, and client
resource-ownership contracts. Expected negative cases are successful demonstrations rather than
uncontrolled tracebacks.

## Pull, start, and stop the disposable Java services

Compose contains only `dpp-repo-api` on host port 8080 and `dpp-registry-api` on host port 8081.
The images' application defaults select memory mode. The file defines no persistence service or
volume. Use a unique project name so repeated runs cannot attach to stale demo containers.

PowerShell:

```powershell
$project = "dpp-py-demo-$([guid]::NewGuid().ToString('N'))"
$env:DPP_DEMO_PROJECT = $project
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env pull
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env up -d --wait --wait-timeout 120
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env ps --all
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env down --remove-orphans
```

Linux/macOS:

```bash
project="dpp-py-demo-$(python -c 'import uuid; print(uuid.uuid4().hex)')"
export DPP_DEMO_PROJECT="$project"
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env pull
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env up -d --wait --wait-timeout 120
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env ps --all
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env down --remove-orphans
```

Replace `pinned.env` with `0.5.0.env` for the required maintained-release profile. Container
health is only a startup dependency; the future runner will also poll both public clients'
functional health checks before interoperability scenarios.

If startup or verification fails, capture evidence before cleanup:

```powershell
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env ps --all
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env logs --no-color --timestamps
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env images --format json
docker compose -p $env:DPP_DEMO_PROJECT --env-file .\env\pinned.env down --remove-orphans
```

```bash
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env ps --all
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env logs --no-color --timestamps
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env images --format json
docker compose -p "$DPP_DEMO_PROJECT" --env-file ./env/pinned.env down --remove-orphans
```

## Runner modes in this foundation

| Mode | Current behavior | Exit status |
|---|---|---|
| `sdk` | Runs and asserts SDK-01 through SDK-15 | Zero when all pass |
| `services` | Reports live Java interoperability as next-phase `NOT_IMPLEMENTED` | Nonzero |
| `all` | Runs SDK scenarios, then reports the live phase limitation | Nonzero |
| `verify` | Runs assertion-based SDK-only partial verification and reports the live limitation | Nonzero |

The normal future release command remains:

```powershell
.\.venv\Scripts\python.exe -m dpp_java_services_demo verify
```

The optional legacy form is explicit and remains non-blocking:

```powershell
.\.venv\Scripts\python.exe -m dpp_java_services_demo verify --env-file env\0.4.0.env --legacy
```

Both commands exit nonzero in this foundation because live interoperability is not yet
implemented. No current output should be interpreted as repository or registry interoperability
success.

## Test and packaging boundaries

Run demo unit tests independently:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

```bash
./.venv/bin/python -m pytest
```

Ordinary root `pytest` does not discover this nested test project and does not require Docker.
The root wheel and source distribution intentionally exclude `examples/java-services-demo`.
Future Docker-dependent tests will be separately marked and will fail, not silently skip, when
an explicit integration flag is supplied but the services are unavailable.

## Limitations

- Live repository and registry scenarios, readiness polling, cleanup orchestration, image digest
  recording/comparison, and release reports are next-phase work.
- Only disposable local Java containers are supported. Shared long-lived endpoints are out of
  scope.
- Native arm64 images are not a current completion requirement.
- The demo does not provide persistence, PostgreSQL, EDC, dataspace, or backend functionality.
- Passing demo coverage is evidence for the scenarios executed; it is not a claim of 100%
  compatibility.
