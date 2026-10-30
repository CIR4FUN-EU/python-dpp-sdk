# Advanced mock-services operations and troubleshooting

The [demo README](README.md) covers the normal path. This page has extra commands for ports,
other service versions, diagnosis, cleanup, and maintainer verification.

**Run from:** the repository root (the folder that contains the root `pyproject.toml`), with the
development environment activated.

## Set up the variables first

The commands on this page use the variables below. Run this block once in each new terminal
before any other block.

PowerShell:

```powershell
$demoDir = (Resolve-Path .\examples\mock-services-demo).Path
$envFile = Join-Path $demoDir ".env"
$composeFile = Join-Path $demoDir "compose.yaml"
$project = "dpp-mock-services-demo-local"
```

Bash (Linux/macOS):

```bash
demo_dir="$(cd ./examples/mock-services-demo && pwd)"
env_file="$demo_dir/.env"
compose_file="$demo_dir/compose.yaml"
project="dpp-mock-services-demo-local"
```

## Alternate ports

The demo's `.env` (created from `.env.example`) uses port 18080 for the repository and 18081 for the
registry. Without an `.env` file, as in the README quickstart, `compose.yaml` falls back to 8080 and
8081. If your ports are taken, set all six values together, then start the services again. You can
also put the same values into `.env`.

PowerShell:

```powershell
$env:DPP_REPO_PORT = "28080"
$env:DPP_REGISTRY_PORT = "28081"
$env:MOCK_REPO_PORT = "28080"
$env:MOCK_REGISTRY_PORT = "28081"
$env:DPP_REPO_BASE_URL = "http://localhost:28080"
$env:DPP_REGISTRY_BASE_URL = "http://localhost:28081"
```

Linux/macOS:

```bash
export DPP_REPO_PORT=28080
export DPP_REGISTRY_PORT=28081
export MOCK_REPO_PORT=28080
export MOCK_REGISTRY_PORT=28081
export DPP_REPO_BASE_URL=http://localhost:28080
export DPP_REGISTRY_BASE_URL=http://localhost:28081
```

The example uses 28080 and 28081; replace them with any free port numbers.

## Other service versions

By default, the images set in [compose.yaml](compose.yaml) are used. To run against another
service version, set `$envFile` (PowerShell) or `env_file` (Bash) to one of the profiles in the
`env/` folder. Each file name states the version. The `pinned.env` profile pins exact image digests.
A missing profile file is reported as an error; nothing else is used silently in its place.
Keeping a profile in the repository does not guarantee that its images are publicly pullable.

## Optional PowerShell lifecycle helper

`manage-mock-services.ps1` checks the configuration, pulls missing images, waits until the
services are healthy, and keeps every action inside the selected project:

```powershell
docker compose --env-file $envFile -f $composeFile -p $project pull
& (Join-Path $demoDir "manage-mock-services.ps1") -Action Start -EnvFile $envFile -Project $project
& (Join-Path $demoDir "manage-mock-services.ps1") -Action Status -EnvFile $envFile -Project $project
& (Join-Path $demoDir "manage-mock-services.ps1") -Action Logs -EnvFile $envFile -Project $project
& (Join-Path $demoDir "manage-mock-services.ps1") -Action Stop -EnvFile $envFile -Project $project
```

`Stop` keeps the stored data. `Delete` removes it and requires `-ConfirmDelete`. Check the project
name before you use it.

## Project-scoped diagnosis

Always use the same project name, compose file, and `.env` as when you started the services.
These commands show the containers, their logs, and the final configuration:

PowerShell:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile ps --all
docker compose -f $composeFile -p $project --env-file $envFile logs --no-color --timestamps
docker compose -f $composeFile -p $project --env-file $envFile config
```

Linux/macOS:

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" ps --all
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" logs --no-color --timestamps
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" config
```

Common problems:

- **Docker is not available:** start Docker Desktop or Docker Engine.
- **Pull is rejected:** check that you can reach `ghcr.io` and that the selected profile exists.
- **Port is already in use:** see [alternate ports](#alternate-ports), then start the services again.
- **Services never become healthy:** save the `ps` and `logs` output before you stop anything.
- **`demo` is missing from `--help`:** reinstall the SDK and the demo package
  (`python -m pip install --force-reinstall -e . -e ./examples/mock-services-demo`).
- **Package provenance mismatch:** rebuild and force-reinstall the SDK wheel passed with `--sdk-wheel`.
- **Image check finds no container:** make sure the services were started with the same project
  name you pass to `verify`.

## Cleanup choices

These commands affect only the named demo project.

Stop and remove the containers, but keep the stored data:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile down --remove-orphans
```

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" down --remove-orphans
```

Stop and remove everything, **including the stored data**:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile down --volumes --remove-orphans
```

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" down --volumes --remove-orphans
```

## Choose a verification level

- **SDK development:** run the root pytest suite with `-m "not integration"`.
- **Demo development:** run the demo pytest suite with `-m "not integration"`.
- **Connected integration:** `python -m dpp_mock_services_demo.maintainer live --env-file <file>`
  runs the 19 live scenarios once.
- **Full release confidence:** use the full-verification flow below. It runs
  both non-live suites, then strict clean-wheel verification and the 19 live scenarios once.

## Optional maintainer verification

Keep the connected Compose project running for these commands.

```powershell
python -m dpp_mock_services_demo.maintainer sdk-contracts
python -m dpp_mock_services_demo.maintainer live --env-file $envFile

python -m build --outdir .\artifacts\root
$sdkWheel = (Get-ChildItem .\artifacts\root\dpp_sdk-*.whl | Select-Object -First 1).FullName
$report = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-demo-verify-$PID.json"
python -m dpp_mock_services_demo.maintainer verify `
  --env-file $envFile --compose-project $project --sdk-wheel $sdkWheel --report-file $report
```

```bash
python -m dpp_mock_services_demo.maintainer sdk-contracts
python -m dpp_mock_services_demo.maintainer live --env-file "$env_file"

mkdir -p artifacts/root
python -m build --outdir artifacts/root
set -- artifacts/root/dpp_sdk-*.whl
sdk_wheel="$1"
report="${TMPDIR:-/tmp}/dpp-demo-verify-$$.json"
python -m dpp_mock_services_demo.maintainer verify \
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
python -m build --outdir $artifacts
python -m build .\examples\mock-services-demo --outdir $artifacts
$sdkWheel = (Get-ChildItem $artifacts\dpp_sdk-*.whl | Select-Object -First 1).FullName
$demoWheel = (Get-ChildItem $artifacts\dpp_sdk_mock_services_demo-*.whl | Select-Object -First 1).FullName
$verifyVenv = Join-Path (Resolve-Path .).Path ".verify-venv"
if (-not (Test-Path (Join-Path $verifyVenv "Scripts\python.exe"))) {
  python -m venv $verifyVenv
}
$verifyPython = Join-Path $verifyVenv "Scripts\python.exe"
& $verifyPython -m pip install --upgrade pip
& $verifyPython -m pip install --force-reinstall $sdkWheel $demoWheel

python -m pytest .\tests --run-mock-services --force-sugar
python -m pytest -c .\examples\mock-services-demo\pyproject.toml `
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
python -m build --outdir "$artifacts"
python -m build ./examples/mock-services-demo --outdir "$artifacts"
set -- "$artifacts"/dpp_sdk-*.whl
sdk_wheel="$1"
set -- "$artifacts"/dpp_sdk_mock_services_demo-*.whl
demo_wheel="$1"
verify_venv=.verify-venv
[ -x "$verify_venv/bin/python" ] || python -m venv "$verify_venv"
verify_python="$verify_venv/bin/python"
"$verify_python" -m pip install --upgrade pip
"$verify_python" -m pip install --force-reinstall "$sdk_wheel" "$demo_wheel"

python -m pytest ./tests --run-mock-services --force-sugar
python -m pytest \
  -c ./examples/mock-services-demo/pyproject.toml \
  ./examples/mock-services-demo/tests \
  --run-mock-services --force-sugar
report="${TMPDIR:-/tmp}/dpp-demo-verify-$$.json"
(cd "${TMPDIR:-/tmp}" && "$verify_python" -I -m dpp_mock_services_demo.maintainer verify \
  --env-file "$env_file" --compose-project "$project" --sdk-wheel "$sdk_wheel" \
  --report-file "$report" --summary)
```
