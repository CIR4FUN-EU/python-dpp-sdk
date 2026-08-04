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
and GHCR access are not prerequisites for ordinary SDK use. **Run from:** the Python repository
root. Every command in this guide uses a path relative to that root.

Build both projects from the Python repository root, then install their wheels into a clean
environment. **Prerequisites:** the root `.venv` development environment contains the configured
build tool. This deliberately avoids an editable install or a root `src` path.

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m build .\examples\java-services-demo `
  --outdir .\examples\java-services-demo\dist
.\.venv\Scripts\python.exe -m venv .\.java-services-demo-venv
.\.java-services-demo-venv\Scripts\python.exe -m pip install `
  .\dist\dpp_sdk-0.2.1-py3-none-any.whl `
  .\examples\java-services-demo\dist\dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl
```

Linux/macOS:

```bash
.venv/bin/python -m build
.venv/bin/python -m build ./examples/java-services-demo \
  --outdir ./examples/java-services-demo/dist
.venv/bin/python -m venv ./.java-services-demo-venv
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

These `sdk` commands do not read an environment profile or require Docker, Compose, service URLs,
or image references. The `services`, `all`, and `verify` modes are service-dependent and require
either `--env-file` or a discoverable local demo profile. For those modes, values resolve in this
order: process environment overrides the selected environment profile, and the profile supplies
the documented defaults. A missing service profile is reported as a mode-specific configuration
error.

## Pull, start, verify, capture, and stop

Compose mirrors the Java demo topology: public pulled repository and registry API images, plus
disposable `postgres:16` containers for each API. The public image references always come from
the selected `env/*.env` profile. The database names, users, and passwords are Java demo-local
defaults only; do not use this stack with production credentials or shared endpoints.

Compose derives container and volume names from the project name; it does not set fixed
`container_name` values. Create a unique project name for each local run. Do not reuse a project
you did not create. The teardown below removes only the project created by this guide.

PowerShell, from the Python repository root:

```powershell
$project = "dpp-java-services-demo-$PID"
$composeFile = (Resolve-Path .\examples\java-services-demo\compose.yaml).Path
$envFile = (Resolve-Path .\examples\java-services-demo\env\pinned.env).Path
$report = Join-Path (Resolve-Path .\examples\java-services-demo).Path "verification-report.json"
$demoPython = (Resolve-Path .\.java-services-demo-venv\Scripts\python.exe).Path
$sdkWheel = (Resolve-Path .\dist\dpp_sdk-0.2.1-py3-none-any.whl).Path
$repoUrl = if ($env:DPP_REPO_BASE_URL) { $env:DPP_REPO_BASE_URL } else { "http://localhost:8080" }
$registryUrl = if ($env:DPP_REGISTRY_BASE_URL) { $env:DPP_REGISTRY_BASE_URL } else { "http://localhost:8081" }

docker compose -f $composeFile -p $project --env-file $envFile pull
docker compose -f $composeFile -p $project --env-file $envFile up -d --wait --wait-timeout 120
docker compose -f $composeFile -p $project --env-file $envFile ps --all
Invoke-WebRequest "$repoUrl/health" | Select-Object -ExpandProperty StatusCode
Invoke-WebRequest "$registryUrl/health" | Select-Object -ExpandProperty StatusCode

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

Linux/macOS, from the Python repository root:

```bash
project="dpp-java-services-demo-$$"
demo_dir="$(pwd)/examples/java-services-demo"
compose_file="$demo_dir/compose.yaml"
env_file="$demo_dir/env/pinned.env"
report="$demo_dir/verification-report.json"
demo_python="$(pwd)/.java-services-demo-venv/bin/python"
sdk_wheel="$(pwd)/dist/dpp_sdk-0.2.1-py3-none-any.whl"
repo_url="${DPP_REPO_BASE_URL:-http://localhost:8080}"
registry_url="${DPP_REGISTRY_BASE_URL:-http://localhost:8081}"

docker compose -f "$compose_file" -p "$project" --env-file "$env_file" pull
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" up -d --wait --wait-timeout 120
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" ps --all
curl --fail "$repo_url/health"
curl --fail "$registry_url/health"

outside="$(mktemp -d)"
(cd "$outside" && "$demo_python" -I \
  -m dpp_java_services_demo verify --env-file "$env_file" \
  --compose-project "$project" --sdk-wheel "$sdk_wheel" --report-file "$report")
rmdir "$outside"
```

On failure, preserve service state and logs before teardown:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile ps --all
docker compose -f $composeFile -p $project --env-file $envFile logs --no-color --timestamps
docker compose -f $composeFile -p $project --env-file $envFile images --format json
docker compose -f $composeFile -p $project --env-file $envFile down --volumes --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" ps --all
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" logs --no-color --timestamps
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" images --format json
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" down --volumes --remove-orphans
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

Run `down --volumes --remove-orphans` only for the project created by this guide. It deletes that
project's disposable database volumes; it must never be aimed at a shared or pre-existing project.

Compose image health starts the dependency chain, while the runner independently polls both
public `/health` operations up to `DPP_STARTUP_TIMEOUT_SECONDS`. A supplied integration flag or
live CLI mode fails when functional readiness is unavailable; it never silently passes.

If Docker or Compose is unavailable, install/enable Docker Desktop or the Docker Engine before
retrying. If `pull` fails, confirm GHCR network access and the selected profile. If a host port is
occupied, apply the alternate-port variables below before `pull` and keep the chosen project name.
If readiness fails, run the project-scoped `ps` and `logs` commands below before teardown.

## Run service-backed modes

After readiness succeeds, run one mode from the Python repository root. `services` exercises live
repository/registry scenarios; `all` adds SDK scenarios; `verify` also writes the required image
and installed-wheel evidence. A missing profile is reported as a configuration error; do not use
live pytest until the stack is healthy and the explicit opt-in flag is present.

PowerShell:

```powershell
& $demoPython -I -m dpp_java_services_demo services --env-file $envFile --json
& $demoPython -I -m dpp_java_services_demo all --env-file $envFile --json
& $demoPython -I -m dpp_java_services_demo verify --env-file $envFile `
  --compose-project $project --sdk-wheel $sdkWheel --report-file $report
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo\tests --run-java-services
```

Linux/macOS:

```bash
"$demo_python" -I -m dpp_java_services_demo services --env-file "$env_file" --json
"$demo_python" -I -m dpp_java_services_demo all --env-file "$env_file" --json
"$demo_python" -I -m dpp_java_services_demo verify --env-file "$env_file" \
  --compose-project "$project" --sdk-wheel "$sdk_wheel" --report-file "$report"
.venv/bin/python -m pytest ./examples/java-services-demo/tests --run-java-services
```

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

Run this from the Python repository root after the maintained setup has defined
`$project`/`$sdkWheel` or `project`/`sdk_wheel` and installed the demo wheel. It is optional and
never a release gate.

```powershell
& $demoPython -I -m dpp_java_services_demo verify `
  --env-file .\examples\java-services-demo\env\0.4.0.env --legacy `
  --compose-project $project --sdk-wheel $sdkWheel `
  --report-file .\examples\java-services-demo\legacy-verification-report.json
```

```bash
"$demo_python" -I -m dpp_java_services_demo verify \
  --env-file ./examples/java-services-demo/env/0.4.0.env --legacy \
  --compose-project "$project" --sdk-wheel "$sdk_wheel" \
  --report-file ./examples/java-services-demo/legacy-verification-report.json
```

Version 0.4.0 is never part of the required pull-request or release gate.

## Test boundary and retained reports

## Validate the demo

Run every command from `Dpp-SDK-python/dpp-python-sdk`. Ordinary tests and collection do not
contact Docker or Java services; live tests require a separately created, healthy project and the
explicit opt-in flag.

```powershell
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo --collect-only
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo --run-java-services
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m build .\examples\java-services-demo --outdir .\examples\java-services-demo\dist
.\.venv\Scripts\python.exe -m twine check dist\* .\examples\java-services-demo\dist\*
docker compose -f .\examples\java-services-demo\compose.yaml --env-file .\examples\java-services-demo\env\pinned.env config --quiet
```

For installed-wheel proof, use the isolated-wheel setup above, then run `sdk --json` from a
temporary directory with `-I`. Docker is required only for Compose, live tests, `services`, `all`,
and `verify`; use logs and project-scoped teardown from the lifecycle section after a live run.

`REG-09` (registry read-back) and `REG-10` (registry cleanup) are explicitly unsupported public
operations: their Java routes are internal helpers and the Python SDK intentionally exposes no
client methods for them.

Ordinary root `pytest` does not collect this nested project or require Docker. Run the nested
project explicitly from the Python repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo
.\.venv\Scripts\python.exe -m pytest .\examples\java-services-demo --run-java-services
```

```bash
.venv/bin/python -m pytest ./examples/java-services-demo
.venv/bin/python -m pytest ./examples/java-services-demo --run-java-services
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
