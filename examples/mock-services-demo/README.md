# Python SDK repository/registry services demo

This consumer example uses the public Python SDK against disposable repository
and registry mock-service images. It does not add service behavior to the SDK.

**Run from:** the Python repository root. Python 3.11+ is required. Docker is
needed only for connected commands.

## Quick start

Run the offline SDK walkthrough. The offline example does not load a service profile or contact
Docker. It covers representative `SDK-01`, `SDK-02`, `SDK-03`, `SDK-06`, and `SDK-07` scenarios.
Read the annotated [sdk_scenarios.py](src/dpp_mock_services_demo/sdk_scenarios.py)
source to see the SDK calls behind those cases.

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,release]"
& .\.venv\Scripts\python.exe -m pip install -e .\examples\mock-services-demo
& .\.venv\Scripts\python.exe -m dpp_mock_services_demo sdk
```

## Optional connected demo

Create one local environment file. Select unique paired ports and base URLs in
that file before starting services.

```powershell
$demoDir = (Resolve-Path .\examples\mock-services-demo).Path
$envFile = Join-Path $demoDir ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
  Copy-Item (Join-Path $demoDir ".env.example") $envFile
}
```

Start services, run the connected demo, then remove the disposable project.
Cleanup is project-scoped because every Compose command uses `$project`:
Compose creates project-prefixed container names for this isolated stack.
Docker Engine or Docker Desktop must be running before these commands.
Read the annotated [integration_scenarios.py](src/dpp_mock_services_demo/integration_scenarios.py)
source to see the public client calls and cleanup sequence.

```powershell
$composeFile = Join-Path $demoDir "compose.yaml"
$project = "dpp-mock-services-demo-local"
docker compose --env-file $envFile -f $composeFile -p $project pull
docker compose --env-file $envFile -f $composeFile -p $project up -d --wait
& .\.venv\Scripts\python.exe -m dpp_mock_services_demo demo --env-file $envFile
docker compose --env-file $envFile -f $composeFile -p $project down -v
```

The direct Compose commands are cross-platform. The PowerShell-only
`manage-mock-services.ps1` is an Optional PowerShell convenience wrapper and
does not depend on PowerShell script execution policy beyond the current process:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& (Join-Path $demoDir "manage-mock-services.ps1") -Action Start -EnvFile $envFile
```


## Linux/macOS

Run the same commands from Bash or a compatible shell.

```bash
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -e ".[dev,release]"
.venv/bin/python -m pip install -e ./examples/mock-services-demo
.venv/bin/python -m dpp_mock_services_demo sdk

demo_dir="$(cd ./examples/mock-services-demo && pwd)"
env_file="$demo_dir/.env"
if [ ! -f "$env_file" ]; then
  cp "$demo_dir/.env.example" "$env_file"
fi

compose_file="$demo_dir/compose.yaml"
project="dpp-mock-services-demo-local"
docker compose --env-file "$env_file" -f "$compose_file" -p "$project" pull
docker compose --env-file "$env_file" -f "$compose_file" -p "$project" up -d --wait
.venv/bin/python -m dpp_mock_services_demo demo --env-file "$env_file"
docker compose --env-file "$env_file" -f "$compose_file" -p "$project" down -v
```

## Optional maintainer verification

Keep the connected Compose project running for these commands.

```powershell
& .\.venv\Scripts\python.exe -m dpp_mock_services_demo.maintainer sdk-contracts
& .\.venv\Scripts\python.exe -m dpp_mock_services_demo.maintainer live --env-file $envFile

& .\.venv\Scripts\python.exe -m build --outdir .\artifacts\root
$sdkWheel = (Get-ChildItem .\artifacts\root\dpp_sdk-*.whl | Select-Object -First 1).FullName
$report = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-demo-verify-$PID.json"
& .\.venv\Scripts\python.exe -m dpp_mock_services_demo.maintainer verify `
  --env-file $envFile --compose-project $project --sdk-wheel $sdkWheel --report-file $report
```

```bash
.venv/bin/python -m dpp_mock_services_demo.maintainer sdk-contracts
.venv/bin/python -m dpp_mock_services_demo.maintainer live --env-file "$env_file"

mkdir -p artifacts/root
.venv/bin/python -m build --outdir artifacts/root
set -- artifacts/root/dpp_sdk-*.whl
sdk_wheel="$1"
report="${TMPDIR:-/tmp}/dpp-demo-verify-$$.json"
.venv/bin/python -m dpp_mock_services_demo.maintainer verify \
  --env-file "$env_file" --compose-project "$project" --sdk-wheel "$sdk_wheel" --report-file "$report"
```

## Full SDK and live service test suites

Keep the mock services running and use the same environment file for both
commands. Together they run the full root SDK suite, the complete demo suite,
and every opt-in live test.

```powershell
$env:DPP_DEMO_ENV_FILE = (Resolve-Path $envFile).Path
$demoConfig = Get-Content $envFile -Raw | ConvertFrom-StringData
$env:DPP_REPO_BASE_URL = $demoConfig.DPP_REPO_BASE_URL
$env:DPP_REGISTRY_BASE_URL = $demoConfig.DPP_REGISTRY_BASE_URL

$artifacts = Join-Path (Resolve-Path .).Path "artifacts\verification"
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
& .\.venv\Scripts\python.exe -m build --outdir $artifacts
& .\.venv\Scripts\python.exe -m build .\examples\mock-services-demo --outdir $artifacts
$sdkWheel = (Get-ChildItem $artifacts\dpp_sdk-*.whl | Select-Object -First 1).FullName
$demoWheel = (Get-ChildItem $artifacts\dpp_sdk_mock_services_demo-*.whl | Select-Object -First 1).FullName
$verifyVenv = Join-Path (Resolve-Path .).Path ".verify-venv"
if (-not (Test-Path (Join-Path $verifyVenv "Scripts\python.exe"))) {
  & .\.venv\Scripts\python.exe -m venv $verifyVenv
}
$verifyPython = Join-Path $verifyVenv "Scripts\python.exe"
& $verifyPython -m pip install --upgrade pip
& $verifyPython -m pip install --force-reinstall $sdkWheel $demoWheel

& .\.venv\Scripts\python.exe -m pytest .\tests --run-mock-services --force-sugar
& .\.venv\Scripts\python.exe -m pytest -c .\examples\mock-services-demo\pyproject.toml `
  .\examples\mock-services-demo\tests `
  --run-mock-services --force-sugar
$report = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-demo-verify-$PID.json"
Push-Location ([System.IO.Path]::GetTempPath())
try {
  & $verifyPython -I -m dpp_mock_services_demo.maintainer verify `
    --env-file $envFile --compose-project $project --sdk-wheel $sdkWheel `
    --report-file $report --summary
} finally {
  Pop-Location
}
```

```bash
DPP_DEMO_ENV_FILE="$env_file"
export DPP_DEMO_ENV_FILE
export DPP_REPO_BASE_URL="$(sed -n 's/^DPP_REPO_BASE_URL=//p' "$env_file" | head -n 1)"
export DPP_REGISTRY_BASE_URL="$(sed -n 's/^DPP_REGISTRY_BASE_URL=//p' "$env_file" | head -n 1)"

artifacts=./artifacts/verification
mkdir -p "$artifacts"
.venv/bin/python -m build --outdir "$artifacts"
.venv/bin/python -m build ./examples/mock-services-demo --outdir "$artifacts"
set -- "$artifacts"/dpp_sdk-*.whl
sdk_wheel="$1"
set -- "$artifacts"/dpp_sdk_mock_services_demo-*.whl
demo_wheel="$1"
verify_venv=.verify-venv
[ -x "$verify_venv/bin/python" ] || .venv/bin/python -m venv "$verify_venv"
verify_python="$verify_venv/bin/python"
"$verify_python" -m pip install --upgrade pip
"$verify_python" -m pip install --force-reinstall "$sdk_wheel" "$demo_wheel"

.venv/bin/python -m pytest ./tests --run-mock-services --force-sugar
.venv/bin/python -m pytest \
  -c ./examples/mock-services-demo/pyproject.toml \
  ./examples/mock-services-demo/tests \
  --run-mock-services --force-sugar
report="${TMPDIR:-/tmp}/dpp-demo-verify-$$.json"
(cd "${TMPDIR:-/tmp}" && "$verify_python" -I -m dpp_mock_services_demo.maintainer verify \
  --env-file "$env_file" --compose-project "$project" --sdk-wheel "$sdk_wheel" \
  --report-file "$report" --summary)
```

For extra lifecycle commands, troubleshooting, alternate profiles, logs, and
cleanup options, see [ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md). This is
an optional troubleshooting reference, not the normal demo path.
