# Python SDK repository/registry services demo

This is a small consumer example for the Python SDK. It uses the public SDK
models, validation, JSON codec, immutable updates, `DppRepoClient`, and
`DppRegistryClient`. The supplied Compose profiles currently run Java service
images; the Python demo communicates with them only through their HTTP APIs.

**Run from:** the Python repository root.

## Quick start

Python 3.11+ is required. Docker Engine or Docker Desktop must be installed and
running only for the connected `demo` command.

Create a development environment and run the representative offline SDK example:

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,release]"
& .\.venv\Scripts\python.exe -m pip install -e .\examples\java-services-demo
& .\.venv\Scripts\python.exe -m dpp_java_services_demo sdk
```

The offline example does not load a service profile or contact Docker.
It runs the representative `SDK-01`, `SDK-02`, `SDK-03`, `SDK-06`, and `SDK-07` cases;
the complete `SDK-01` through `SDK-17` contract matrix is maintainer verification.

## Optional connected demo

The committed default profile intentionally names the forthcoming `0.5.1`
images. For current live testing, use `env/0.5.0.env`; leave the default and
example configuration at `0.5.1` for the release.

Copy the local environment file once and select unique paired ports/base URLs if
needed:

```powershell
$demoDir = (Resolve-Path .\examples\java-services-demo).Path
$envFile = Join-Path $demoDir ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
  Copy-Item (Join-Path $demoDir ".env.example") $envFile
}
```

Start the services with Docker Compose directly. This is the primary,
cross-platform lifecycle command and does not depend on PowerShell script execution policy.
Docker Engine or Docker Desktop must be running; Compose
creates project-prefixed container names:

```powershell
$composeFile = Join-Path $demoDir "compose.yaml"
$project = "dpp-java-services-demo-local"
docker compose --env-file $envFile -f $composeFile -p $project pull
docker compose --env-file $envFile -f $composeFile -p $project up -d --wait
& .\.venv\Scripts\python.exe -m dpp_java_services_demo demo --env-file $envFile
docker compose --env-file $envFile -f $composeFile -p $project down -v
```

For a current image run, replace `$envFile` above with
`(Resolve-Path .\examples\java-services-demo\env\0.5.0.env).Path`. Cleanup is
project-scoped; do not omit `-p $project`.

`manage-java-services.ps1` remains an Optional PowerShell convenience wrapper. On Windows
systems that permit local scripts, invoke it for the same lifecycle:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& (Join-Path $demoDir "manage-java-services.ps1") -Action Start -EnvFile $envFile
```

## Optional maintainer verification

The exhaustive SDK cases, full repository/registry live matrix, controlled HTTP
contracts, wheel provenance, image identity, and CI evidence are maintainer
responsibilities, not normal demo steps:

```powershell
& .\.venv\Scripts\python.exe -m dpp_java_services_demo.maintainer sdk-contracts
& .\.venv\Scripts\python.exe -m dpp_java_services_demo.maintainer live --env-file $envFile
```

For the optional strict verification, first build the root wheel and keep the
connected Compose project running. It runs all SDK, controlled HTTP, and live
service checks, then verifies wheel provenance and image identity:

```powershell
& .\.venv\Scripts\python.exe -m build --outdir .\artifacts\root
$sdkWheel = (Get-ChildItem .\artifacts\root\dpp_sdk-*.whl | Select-Object -First 1).FullName
$report = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-demo-verify-$PID.json"
& .\.venv\Scripts\python.exe -m dpp_java_services_demo.maintainer verify `
  --env-file $envFile --compose-project $project --sdk-wheel $sdkWheel --report-file $report
```

Run the separate, opt-in pytest live matrix only against already-running
services:

```powershell
$env:DPP_DEMO_ENV_FILE = (Resolve-Path .\examples\java-services-demo\env\0.5.0.env).Path
& .\.venv\Scripts\python.exe -m pytest -q -c .\examples\java-services-demo\pyproject.toml `
  .\examples\java-services-demo\tests\verification\test_live_contract_matrix.py `
  --run-java-services
```

Existing `full`, `verify`, `integration`, `services`, and `all` demo commands
remain compatibility paths. See [OPERATIONS.md](OPERATIONS.md) for advanced
diagnosis and CI behavior.
