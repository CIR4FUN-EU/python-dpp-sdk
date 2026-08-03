# Python SDK Java-services demo

This is an isolated, unpublished consumer of the public `dpp-sdk` package. Use it when you want to
see the Python clients talk to disposable Java DPP repository and registry services. It adds no
backend, persistence, Docker, demo-service, EDC, or dataspace responsibility to `dpp_sdk`.
Compose starts the Java-compatible PostgreSQL containers required by the pulled Java API images; it
does not add a Python persistence implementation.

The CLI never pulls, starts, stops, or removes containers. The operator or CI workflow owns the
entire Compose lifecycle.

## Relationship to the SDK guides

This demo consumes the installed public SDK; it is not a service implementation or an extension of
the `dpp_sdk` import package. Read [SDK usage](../../docs/usage.md) for SDK-only construction and
codec examples, [Clients](../../src/dpp_sdk/clients/README.md) for the public repository and registry
client operations exercised here, and the root [README](../../README.md) for scope and module links.

## Compatibility and evidence policy

[`env/pinned.env`](env/pinned.env) is the required reproducible default and uses immutable
tag-plus-digest references. [`env/0.5.0.env`](env/0.5.0.env) is the maintained semantic-version
profile. Every `verify` run records the locally executed image digests, freshly resolves the
remote `0.5.0` digests, and classifies them as `SAME_BUILD` or `DIFFERENT_BUILD`. Historical
digest equality is never assumed.

> The demo is maintained against Java repository and registry version 0.5.0 and the recorded
> immutable image digest. Version 0.4.0 is retained as an optional legacy compatibility target
> and is not part of the maintained compatibility guarantee.

[`env/0.4.0.env`](env/0.4.0.env) requires `--legacy`. Its live scenarios are reported as
`LEGACY_040`, and its aggregate outcome is exactly `LEGACY_COMPATIBILITY_PASSED` or
`LEGACY_COMPATIBILITY_FAILED`; otherwise reports use `LEGACY_COMPATIBILITY_NOT_RUN`. A legacy
failure is informational: it is not a current Python SDK defect, current contract mismatch,
release blocker, or reason to add compatibility shims.

Passing these scenarios is interoperability evidence for the covered contracts, not a claim of
100% compatibility.

## Prerequisites and isolated installation

Choose the mode first:

| If you want to… | You need… |
| --- | --- |
| run the SDK-only checks | Python 3.11 or newer |
| start local Java services, then run `services` or `all` | Python plus Docker Engine with Compose v2 and access to the public GHCR images |
| run the complete `verify` check | the above plus Docker Buildx for the fresh image-digest lookup |

The root [README](../../README.md#prerequisites) lists the same split. Docker, Compose, Buildx,
and GHCR access are not prerequisites for ordinary SDK use.

Build both projects from the Python repository root, then install their wheels into a clean
environment. This deliberately avoids an editable install or a root `src` path.

PowerShell:

```powershell
python -m build
python -m build .\examples\java-services-demo `
  --outdir .\examples\java-services-demo\dist
python -m venv .\.java-services-demo-venv
.\.java-services-demo-venv\Scripts\python.exe -m pip install `
  .\dist\dpp_sdk-0.2.1-py3-none-any.whl `
  .\examples\java-services-demo\dist\dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl
```

Linux/macOS:

```bash
python -m build
python -m build ./examples/java-services-demo \
  --outdir ./examples/java-services-demo/dist
python -m venv ./.java-services-demo-venv
./.java-services-demo-venv/bin/python -m pip install \
  ./dist/dpp_sdk-0.2.1-py3-none-any.whl \
  ./examples/java-services-demo/dist/dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl
```

The nested distribution depends on `dpp-sdk==0.2.1`, contains only
`dpp_java_services_demo`, and is not published. The root SDK wheel and source distribution
exclude this entire example.

## Runner modes

| Mode | Executed evidence | Docker required |
|---|---|---|
| `sdk` | SDK-01 through SDK-15 | No |
| `services` | REP-01 through REP-15 and REG-01 through REG-07 | Running services |
| `all` | SDK scenarios followed by repository and registry scenarios | Running services |
| `verify` | SDK, controlled REP-16–18/REG-08, live, installed-import, and image identity evidence | Running services |

Expected negative cases are passed demonstrations when the exact contracted error occurs.
`FAILED`, `SKIPPED`, and `NOT_IMPLEMENTED` are required verification failures. A maintained
`verify` returns nonzero for any such result. Only the explicitly selected legacy profile makes
scenario failures informational at process-exit level.

SDK-only use:

```powershell
.\.java-services-demo-venv\Scripts\python.exe -m dpp_java_services_demo sdk
.\.java-services-demo-venv\Scripts\python.exe -m dpp_java_services_demo sdk --json
```

```bash
./.java-services-demo-venv/bin/python -m dpp_java_services_demo sdk
./.java-services-demo-venv/bin/python -m dpp_java_services_demo sdk --json
```

These `sdk` commands work from any directory after installation. They do not read an environment
profile or require Docker, Compose, service URLs, or image references. The `services`, `all`, and
`verify` modes are service-dependent and require either `--env-file` or a discoverable local demo
profile. For those modes, values resolve in this order: process environment overrides the selected
environment profile, and the profile supplies the documented defaults. A missing service profile
is reported as a mode-specific configuration error.

## Pull, start, verify, capture, and stop

Compose mirrors the Java demo topology: public pulled repository and registry API images, plus
disposable `postgres:16` containers for each API. The public image references always come from
the selected `env/*.env` profile. The database names, users, and passwords are Java demo-local
defaults only; do not use this stack with production credentials or shared endpoints.

The Java-compatible Compose file uses fixed container names. Before starting it, verify that no
other Java-style demo stack is running, and always reset it with `down --volumes`.

PowerShell, from `examples/java-services-demo`:

```powershell
$project = "dpp-java-services-demo"
$envFile = (Resolve-Path .\env\pinned.env).Path
$report = (Join-Path (Get-Location) "verification-report.json")
$demoPython = (Resolve-Path ..\..\.java-services-demo-venv\Scripts\python.exe).Path
$sdkWheel = (Resolve-Path ..\..\dist\dpp_sdk-0.2.1-py3-none-any.whl).Path

docker compose -p $project --env-file $envFile pull
docker compose -p $project --env-file $envFile up -d --wait --wait-timeout 120
docker compose -p $project --env-file $envFile ps --all

Push-Location ([System.IO.Path]::GetTempPath())
try {
  & $demoPython -I -m dpp_java_services_demo verify `
    --env-file $envFile --compose-project $project --sdk-wheel $sdkWheel `
    --report-file $report
} finally {
  Pop-Location
}
```

Running the resolved interpreter from a temporary directory with `-I` proves the root checkout
is not supplying `dpp_sdk`.

Linux/macOS, from `examples/java-services-demo`:

```bash
project="dpp-java-services-demo"
env_file="$(pwd)/env/pinned.env"
report="$(pwd)/verification-report.json"
demo_python="$(cd ../.. && pwd)/.java-services-demo-venv/bin/python"
sdk_wheel="$(cd ../.. && pwd)/dist/dpp_sdk-0.2.1-py3-none-any.whl"

docker compose -p "$project" --env-file "$env_file" pull
docker compose -p "$project" --env-file "$env_file" up -d --wait --wait-timeout 120
docker compose -p "$project" --env-file "$env_file" ps --all

outside="$(mktemp -d)"
(cd "$outside" && "$demo_python" -I \
  -m dpp_java_services_demo verify --env-file "$env_file" \
  --compose-project "$project" --sdk-wheel "$sdk_wheel" --report-file "$report")
rmdir "$outside"
```

On failure, preserve service state and logs before teardown:

```powershell
docker compose -p $project --env-file $envFile ps --all
docker compose -p $project --env-file $envFile logs --no-color --timestamps
docker compose -p $project --env-file $envFile images --format json
docker compose -p $project --env-file $envFile down --volumes --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

```bash
docker compose -p "$project" --env-file "$env_file" ps --all
docker compose -p "$project" --env-file "$env_file" logs --no-color --timestamps
docker compose -p "$project" --env-file "$env_file" images --format json
docker compose -p "$project" --env-file "$env_file" down --volumes --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

Compose image health starts the dependency chain, while the runner independently polls both
public `/health` operations up to `DPP_STARTUP_TIMEOUT_SECONDS`. A supplied integration flag or
live CLI mode fails when functional readiness is unavailable; it never silently passes.

### View the running Java demo services

These browser links belong to the disposable Java demo services, not to the Python package:

| Service | Browser API guide | Machine-readable health | OpenAPI JSON |
| --- | --- | --- | --- |
| Repository | `http://localhost:8080/` | `http://localhost:8080/health` | `http://localhost:8080/v3/api-docs` |
| Registry | `http://localhost:8081/` | `http://localhost:8081/health` | `http://localhost:8081/v3/api-docs` |

Opening either base URL redirects to that service's Swagger UI. If you use alternate ports, replace
`8080` and `8081` in these links with the ports configured for your run.

If ports 8080/8081 are occupied, override ports and public URLs together before Compose and CLI
execution:

```powershell
$env:DPP_REPO_PORT = "18080"
$env:DPP_REGISTRY_PORT = "18081"
$env:MOCK_REPO_PORT = "18080"
$env:MOCK_REGISTRY_PORT = "18081"
$env:DPP_REPO_BASE_URL = "http://localhost:18080"
$env:DPP_REGISTRY_BASE_URL = "http://localhost:18081"
```

```bash
export DPP_REPO_PORT=18080
export DPP_REGISTRY_PORT=18081
export MOCK_REPO_PORT=18080
export MOCK_REGISTRY_PORT=18081
export DPP_REPO_BASE_URL=http://localhost:18080
export DPP_REGISTRY_BASE_URL=http://localhost:18081
```

## Maintained, semantic-tag, and legacy runs

The release gates are:

1. Full `verify` against `pinned.env`.
2. Full `verify` against `0.5.0.env`.
3. Dynamic identity comparison between the executed images and fresh `0.5.0` resolution.

When the pinned and `0.5.0` digests are `SAME_BUILD`, one complete scenario execution plus the
recorded equality is sufficient to avoid a duplicate run. `DIFFERENT_BUILD` makes the pinned
`verify` blocking until the complete suite runs separately with `env/0.5.0.env`. The manual
workflow performs that conditional second run automatically.

Optional legacy command:

Run this from `examples/java-services-demo` after the maintained setup has defined
`$project`/`$sdkWheel` or `project`/`sdk_wheel` and installed the demo wheel. It is optional and
never a release gate.

```powershell
& $demoPython -I -m dpp_java_services_demo verify --env-file env\0.4.0.env --legacy `
  --compose-project $project --sdk-wheel $sdkWheel `
  --report-file legacy-verification-report.json
```

```bash
"$demo_python" -I -m dpp_java_services_demo verify --env-file env/0.4.0.env --legacy \
  --compose-project "$project" --sdk-wheel "$sdk_wheel" \
  --report-file legacy-verification-report.json
```

Version 0.4.0 is never part of the required pull-request or release gate.

## Test boundary and retained reports

Ordinary root `pytest` does not collect this nested project or require Docker. From the nested
directory:

```powershell
python -m pytest
python -m pytest --run-java-services
```

```bash
python -m pytest
python -m pytest --run-java-services
```

The first command precisely skips the two marked live tests. The second requires already-running
services and converts readiness or scenario failures into test failures.

The JSON report records scenario fields and totals, Python repository/demo commit, contract
baseline, exact configured image references, serving container IDs and image IDs, runtime
digests bound through those containers, fresh maintained digests, exact SDK wheel path/hash and
installed archive hash, exclusions, timestamps, cleanup warnings, legacy status, and one exact
interoperability verdict. The only full maintained success verdict is
`PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED`.

## Limitations

- Only disposable local Java containers are supported; shared or long-lived endpoints are out of
  scope.
- The registry has no public read-back or cleanup API. REG-03 therefore uses successful
  registration plus the missing-DPP rejection as public repository-verification evidence.
- Malformed transports and other unsafe-to-induce behaviors remain controlled Python transport
  tests; the runner does not force the images to emit unnatural responses.
- The unversioned product-history route is controlled legacy evidence only.
- Native arm64 image support is not a completion requirement.
- PostgreSQL is a disposable Java-image runtime dependency only; no Python persistence package,
  backend, EDC, dataspace, or internal Java route is added to `dpp_sdk`.
