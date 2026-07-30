# Python SDK Java-services demo

This is an isolated, unpublished consumer of the public `dpp-sdk` package. It demonstrates the
SDK locally and exercises its public clients against disposable, published Java DPP repository
and registry images. It adds no backend, persistence, Docker, demo-service, EDC, or dataspace
responsibility to `dpp_sdk`.

The CLI never pulls, starts, stops, or removes containers. The operator or CI workflow owns the
entire Compose lifecycle.

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

- Python 3.11 or newer.
- Docker Engine with Compose v2 for live modes.
- Docker Buildx for the fresh remote digest lookup performed by `verify`.
- Access to the public GHCR image references.

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
```

```bash
./.java-services-demo-venv/bin/python -m dpp_java_services_demo sdk
```

## Pull, start, verify, capture, and stop

Compose contains only the Java repository API and registry API in their image-default memory
mode. It declares no database, persistent volume, credentials, or internal API. Use a unique
project name for every run.

PowerShell, from `examples/java-services-demo`:

```powershell
$project = "dpp-py-demo-$([guid]::NewGuid().ToString('N'))"
$envFile = (Resolve-Path .\env\pinned.env).Path
$report = (Join-Path (Get-Location) "verification-report.json")
$demoPython = (Resolve-Path ..\..\.java-services-demo-venv\Scripts\python.exe).Path

docker compose -p $project --env-file $envFile pull
docker compose -p $project --env-file $envFile up -d --wait --wait-timeout 120
docker compose -p $project --env-file $envFile ps --all

Push-Location ([System.IO.Path]::GetTempPath())
try {
  & $demoPython -I -m dpp_java_services_demo verify `
    --env-file $envFile --report-file $report
} finally {
  Pop-Location
}
```

Running the resolved interpreter from a temporary directory with `-I` proves the root checkout
is not supplying `dpp_sdk`.

Linux/macOS, from `examples/java-services-demo`:

```bash
project="dpp-py-demo-$(python -c 'import uuid; print(uuid.uuid4().hex)')"
env_file="$(pwd)/env/pinned.env"
report="$(pwd)/verification-report.json"
demo_python="$(cd ../.. && pwd)/.java-services-demo-venv/bin/python"

docker compose -p "$project" --env-file "$env_file" pull
docker compose -p "$project" --env-file "$env_file" up -d --wait --wait-timeout 120
docker compose -p "$project" --env-file "$env_file" ps --all

outside="$(mktemp -d)"
(cd "$outside" && "$demo_python" -I \
  -m dpp_java_services_demo verify --env-file "$env_file" --report-file "$report")
rmdir "$outside"
```

On failure, preserve service state and logs before teardown:

```powershell
docker compose -p $project --env-file $envFile ps --all
docker compose -p $project --env-file $envFile logs --no-color --timestamps
docker compose -p $project --env-file $envFile images --format json
docker compose -p $project --env-file $envFile down --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

```bash
docker compose -p "$project" --env-file "$env_file" ps --all
docker compose -p "$project" --env-file "$env_file" logs --no-color --timestamps
docker compose -p "$project" --env-file "$env_file" images --format json
docker compose -p "$project" --env-file "$env_file" down --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

Compose image health starts the dependency chain, while the runner independently polls both
public `/health` operations up to `DPP_STARTUP_TIMEOUT_SECONDS`. A supplied integration flag or
live CLI mode fails when functional readiness is unavailable; it never silently passes.

If ports 8080/8081 are occupied, override ports and public URLs together before Compose and CLI
execution:

```powershell
$env:DPP_REPO_PORT = "18080"
$env:DPP_REGISTRY_PORT = "18081"
$env:DPP_REPO_BASE_URL = "http://localhost:18080"
$env:DPP_REGISTRY_BASE_URL = "http://localhost:18081"
```

## Maintained, semantic-tag, and legacy runs

The release gates are:

1. Full `verify` against `pinned.env`.
2. Full `verify` against `0.5.0.env`.
3. Dynamic identity comparison between the executed images and fresh `0.5.0` resolution.

When the pinned and `0.5.0` digests are `SAME_BUILD`, one complete scenario execution plus the
recorded equality is sufficient to avoid a duplicate run. If they are `DIFFERENT_BUILD`, run the
complete suite separately with `env/0.5.0.env`.

Optional legacy command:

```powershell
python -m dpp_java_services_demo verify --env-file env\0.4.0.env --legacy `
  --report-file legacy-verification-report.json
```

```bash
python -m dpp_java_services_demo verify --env-file env/0.4.0.env --legacy \
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

The first command precisely skips the two marked live tests. The second requires already-running
services and converts readiness or scenario failures into test failures.

The JSON report records scenario fields and totals, Python repository/demo commit, contract
baseline, exact configured image references, local runtime digests, fresh maintained digests,
image equivalence, SDK version/location, timestamps, cleanup warnings, legacy status, and one
exact interoperability verdict. The only full maintained success verdict is
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
- Persistence, PostgreSQL, EDC, dataspace, backend, and internal Java routes are excluded.
