# Python SDK Java-services demo

This optional consumer package has four primary modes. Start with the SDK-only walkthrough, then
start Docker and choose the small live demonstration, broad health check, or strict verification.

| Demo | Command | Docker | What it teaches |
|---|---|---:|---|
| SDK-only educational walkthrough | `sdk` | No | Models, validation, JSON codecs, immutable updates, expected errors, and controlled clients (`SDK-01 through SDK-17`) |
| Curated live demonstration | `demo` | Yes | A small connected create, read, update, registry, expected-error, and cleanup journey |
| Full functional integration | `full` | Yes | Every maintained repository and registry operation once, as a broad system-health check |
| Strict verification | `verify` | Yes | SDK, controlled/live services, exact-wheel provenance, and runtime image identity |

`integration`, `services`, and `all` remain compatibility aliases for existing automation. New
commands should use the four primary modes above.

**Run from:** the repository root—the directory containing the root `pyproject.toml`. Use that root,
not the nested demo directory. Advanced profiles, alternate ports, CI behavior, and detailed
diagnosis are in the [operations reference](OPERATIONS.md).

## Before you start

You need:

- Python 3.11 or newer;
- Docker Engine or Docker Desktop with Compose v2 for live modes;
- PowerShell 7 or newer (`pwsh`) for the labelled service lifecycle commands;
- access to the public images named by the selected environment profile.

Copy `.env.example` to an ignored local `.env` before starting Docker. It configures the maintained
Java `0.5.1` image references and alternate host ports for this project. The later Start command pulls
missing configured images and starts the services. The services and database volumes created below are
disposable. Do not use shared endpoints or production credentials.

## Choose your goal

| Goal | Start here | Then run |
| --- | --- | --- |
| Learn the local SDK | [Steps 1–6](#step-6-run-the-sdk-only-educational-walkthrough) | `sdk`; no Docker required. |
| Present a curated connected workflow | [Steps 1–9](#step-9--run-the-live-integration-educational-walkthrough) | `demo`; detailed educational output. |
| Run the broad functional health check | [Steps 1–10](#step-10--run-optional-technical-modes) | `full`; use `full --detailed` for the full operation evidence. |
| Collect exhaustive technical evidence | [Steps 1–10](#step-10--run-optional-technical-modes) | `verify`; includes strict wheel, controlled, and runtime-image evidence. |

This is the reproducible-validation route: it builds and force-installs the exact wheels intentionally,
so a same-version stale installation cannot change the result. The PowerShell journey is first. A complete
Linux/macOS equivalent follows it.

## PowerShell: complete walkthrough

### Step 1 — Open the repository root

Confirm the current directory contains the root project and demo:

```powershell
Get-Item .\pyproject.toml
Get-Item .\examples\java-services-demo\pyproject.toml
```

### Step 2 — Prepare the development environment

Create `.venv` only when it does not already exist, then install the build/test tools:

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,release]"
```

### Step 3 — Build the SDK and demo wheels

```powershell
& .\.venv\Scripts\python.exe -m build
& .\.venv\Scripts\python.exe -m build .\examples\java-services-demo `
  --outdir .\examples\java-services-demo\dist
```

Expected wheel paths for the current versions:

```text
dist/dpp_sdk-0.4.0-py3-none-any.whl
examples/java-services-demo/dist/dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl
```

If project versions change, use the filenames produced by the build instead.

### Step 4 — Install the exact wheels

Create the disposable demo environment if needed. A same-version installation can still be stale:
without `--force-reinstall`, pip can retain an old SDK or demo package after you build new wheels.

```powershell
$demoPython = (Join-Path (Resolve-Path .).Path ".java-services-demo-venv\Scripts\python.exe")
$sdkWheel = (Resolve-Path .\dist\dpp_sdk-0.4.0-py3-none-any.whl).Path
$demoWheel = (Resolve-Path .\examples\java-services-demo\dist\dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl).Path

if (-not (Test-Path $demoPython)) {
  & .\.venv\Scripts\python.exe -m venv .\.java-services-demo-venv
}
& $demoPython -m pip install --force-reinstall $sdkWheel $demoWheel
```

### Step 5 — Prove the installation is current

Do not start Docker until these checks succeed:

```powershell
& $demoPython -m pip check
& $demoPython -m pip show dpp-sdk dpp-sdk-java-services-demo
& $demoPython -I -c "import dpp_sdk, dpp_java_services_demo; print(dpp_sdk.__file__); print(dpp_java_services_demo.__file__)"
& $demoPython -I -m dpp_java_services_demo --help
```

Both import paths must be inside `.java-services-demo-venv\Lib\site-packages`. CLI help must list
`sdk`, `demo`, `full`, and `verify`. If `demo` is absent, follow
[Stale installation](#stale-installation) before continuing.

### Step 6: Run the SDK-only educational walkthrough

This mode does not read a service profile, contact Docker, or use the network.

Detailed teaching output:

```powershell
& $demoPython -I -m dpp_java_services_demo sdk
```

Compact scenario summary:

```powershell
& $demoPython -I -m dpp_java_services_demo sdk --summary
```

Structured JSON (save it, then inspect the beginning):

```powershell
$sdkReport = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-sdk-walkthrough.json"
& $demoPython -I -m dpp_java_services_demo sdk --json --report-file $sdkReport
Get-Content $sdkReport -TotalCount 24
```

The command still prints the complete JSON report. `$sdkReport` keeps the same report in your
temporary-files directory so you can open it, search it, or attach it to an issue without adding a
generated file to the repository.

`PASS` means the intended operation completed. `EXPECTED_ERROR` means the SDK rejected deliberately
invalid input at the documented boundary; that is successful educational evidence, not a failed run.

### Step 7 — Configure one isolated Docker project

Use a unique project name so every lifecycle command targets only this walkthrough:

```powershell
$serviceScript = (Resolve-Path .\examples\java-services-demo\manage-java-services.ps1).Path
$composeFile = (Resolve-Path .\examples\java-services-demo\compose.yaml).Path
$envFile = Join-Path (Resolve-Path .\examples\java-services-demo).Path ".env"
if (Test-Path $envFile) { throw "Keep and edit the existing $envFile; do not overwrite it." }
Copy-Item .\examples\java-services-demo\.env.example $envFile
# Edit COMPOSE_PROJECT_NAME and paired port/base-URL values in $envFile before continuing.
$demoConfig = ConvertFrom-StringData -StringData (
  (Get-Content -LiteralPath $envFile |
    Where-Object { $_ -match '^(COMPOSE_PROJECT_NAME|DPP_REPO_BASE_URL|DPP_REGISTRY_BASE_URL)=' }) -join "`n"
)
$project = $demoConfig.COMPOSE_PROJECT_NAME
$env:DPP_REPO_BASE_URL = $demoConfig.DPP_REPO_BASE_URL
$env:DPP_REGISTRY_BASE_URL = $demoConfig.DPP_REGISTRY_BASE_URL
$report = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-java-services-demo-$PID.json"
```

### Step 8 — Start the isolated Java services

**What this does:** validates the selected Compose profile, pulls only images that are not already
local, starts the named project, waits for Compose readiness, and verifies both public `/health`
endpoints. It does not touch any other Compose project.

```powershell
& $serviceScript -Action Start -EnvFile $envFile
```

### If Windows PowerShell blocks scripts

Do not change your execution policy. Run the following native Docker Compose fallback; it uses the
same `.env`, project, images, ports, and endpoint variables created above.

```powershell
docker compose -f $composeFile -p $project --env-file $envFile config --quiet
docker compose -f $composeFile -p $project --env-file $envFile pull --policy missing
docker compose -f $composeFile -p $project --env-file $envFile up -d --wait --wait-timeout 120
Invoke-RestMethod "$($env:DPP_REPO_BASE_URL)/health"
Invoke-RestMethod "$($env:DPP_REGISTRY_BASE_URL)/health"
```

Expected services are `dpp-repo-db`, `dpp-repo-api`, `dpp-registry-db`, and
`dpp-registry-api`. Both health results must show `status: UP`. Do not run live demos if startup or
readiness fails; capture logs first. Status shows service names such as `dpp-repo-api` and
project-prefixed container names such as `dpp-java-services-demo-local-dpp-repo-api-1`. The prefix
prevents separate demo projects from colliding; it does not hide the service.

### Step 9 — Run the live integration educational walkthrough

Detailed connected journey:

```powershell
& $demoPython -I -m dpp_java_services_demo demo --env-file $envFile
```

Save the same educational JSON evidence in a temporary report:

```powershell
& $demoPython -I -m dpp_java_services_demo demo `
  --env-file $envFile --json --report-file $report
```

Use `verify` for strict package, controlled, and image evidence.

The journey shows each input, public SDK operation, Java service interaction, observed response,
persistence proof, explanation, consumer value, and status. It deletes its repository DPP and proves
the post-delete 404. Registry registration remains because the public registry API has no read-back
or cleanup operation (`REG-09` and `REG-10` are explicitly excluded).

### Step 10 — Run optional technical modes

Broad repository and registry health check:

The default is concise and grouped. Use `--detailed` when you need the full operation evidence.

```powershell
& $demoPython -I -m dpp_java_services_demo full --env-file $envFile
```

Machine-readable full health result:

```powershell
& $demoPython -I -m dpp_java_services_demo full --env-file $envFile --json
```

Strict verification—run last, with the exact project and SDK wheel:

```powershell
& $demoPython -I -m dpp_java_services_demo verify `
  --env-file $envFile `
  --compose-project $project `
  --sdk-wheel $sdkWheel `
  --report-file $report
```

Educational walkthrough success does not replace strict verification. `verify` additionally checks
installed-wheel provenance and Docker runtime image identity and returns nonzero on failure.

### Step 11 — Inspect this project's containers and logs

**What this does:** shows only the named project's containers, then its logs. Run it before cleanup
when startup or verification fails.

```powershell
& $serviceScript -Action Status -EnvFile $envFile
& $serviceScript -Action Logs -EnvFile $envFile
```

### Step 12 — Stop the project and keep database volumes

**What this does:** stops and removes this project's containers and network but keeps its disposable
database volumes, so the project can be restarted later with the same state.

```powershell
& $serviceScript -Action Stop -EnvFile $envFile
```

### Step 13 — Stop the project and delete database volumes

**What this does:** permanently deletes only this project's containers, network, and repository and
registry database volumes. The explicit `-ConfirmDelete` prevents an accidental volume deletion.

```powershell
& $serviceScript -Action Delete -ConfirmDelete -EnvFile $envFile
Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue
```

Both cleanup choices affect only the project created by this guide and identified by `$project`.
Never substitute the name of a shared or user-owned Compose project.

## Linux/macOS: complete walkthrough

Run from the repository root.

This is a Bash walkthrough and requires PowerShell 7 (`pwsh`) for the labelled lifecycle commands.
If `pwsh` is unavailable, use the native Docker Compose diagnosis and cleanup commands in the
[operations reference](OPERATIONS.md); do not mix their shell syntax into the commands below.

### 1 — Prepare, build, and install exact wheels

```bash
test -x .venv/bin/python || python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,release]'
.venv/bin/python -m build
.venv/bin/python -m build ./examples/java-services-demo \
  --outdir ./examples/java-services-demo/dist

demo_python="$(pwd)/.java-services-demo-venv/bin/python"
sdk_wheel="$(pwd)/dist/dpp_sdk-0.4.0-py3-none-any.whl"
demo_wheel="$(pwd)/examples/java-services-demo/dist/dpp_sdk_java_services_demo-0.1.0-py3-none-any.whl"

test -x "$demo_python" || .venv/bin/python -m venv ./.java-services-demo-venv
"$demo_python" -m pip install --force-reinstall "$sdk_wheel" "$demo_wheel"
"$demo_python" -m pip check
"$demo_python" -m pip show dpp-sdk dpp-sdk-java-services-demo
"$demo_python" -I -c 'import dpp_sdk, dpp_java_services_demo; print(dpp_sdk.__file__); print(dpp_java_services_demo.__file__)'
"$demo_python" -I -m dpp_java_services_demo --help
```

Both imports must resolve under `.java-services-demo-venv`; help must list `demo` and `full`.

### 2 — Run SDK-only modes

```bash
"$demo_python" -I -m dpp_java_services_demo sdk
"$demo_python" -I -m dpp_java_services_demo sdk --summary
"$demo_python" -I -m dpp_java_services_demo sdk --json
```

### 3 — Start an isolated Docker project

**What this does:** validates the selected Compose profile, pulls missing images, starts the named
project, and checks both public health endpoints without touching another Compose project.

```bash
demo_dir="$(pwd)/examples/java-services-demo"
service_script="$demo_dir/manage-java-services.ps1"
compose_file="$demo_dir/compose.yaml"
env_file="$demo_dir/.env"
test ! -e "$env_file" || { echo "Keep and edit the existing $env_file; do not overwrite it."; exit 1; }
cp "$demo_dir/.env.example" "$env_file"
# Edit COMPOSE_PROJECT_NAME and paired port/base-URL values in "$env_file" before continuing.
project="dpp-java-services-demo-local" # keep this equal to COMPOSE_PROJECT_NAME in "$env_file"
report="$(mktemp -t dpp-java-services-demo-XXXXXX.json)"
pwsh -File "$service_script" -Action Start -EnvFile "$env_file"
```

### 4 — Run each live mode

```bash
"$demo_python" -I -m dpp_java_services_demo demo --env-file "$env_file"
"$demo_python" -I -m dpp_java_services_demo demo \
  --env-file "$env_file" --json --report-file "$report"
"$demo_python" -I -m dpp_java_services_demo full --env-file "$env_file"
"$demo_python" -I -m dpp_java_services_demo full --env-file "$env_file" --json
"$demo_python" -I -m dpp_java_services_demo verify \
  --env-file "$env_file" \
  --compose-project "$project" \
  --sdk-wheel "$sdk_wheel" \
  --report-file "$report"
```

### 5 — Inspect logs and choose cleanup

Show project status and logs:

```bash
pwsh -File "$service_script" -Action Status -EnvFile "$env_file"
pwsh -File "$service_script" -Action Logs -EnvFile "$env_file"
```

Stop but keep database volumes:

```bash
pwsh -File "$service_script" -Action Stop -EnvFile "$env_file"
```

Delete database volumes and the temporary report permanently:

```bash
pwsh -File "$service_script" -Action Delete -ConfirmDelete -EnvFile "$env_file"
rm -f "$report"
```

## Troubleshooting

### Stale installation

Symptoms include:

- CLI help does not list `demo` and `full`;
- strict verification reports a built-wheel hash different from the installed archive hash;
- output or image-identity behavior does not match current source/tests.

First rerun Step 4 with `--force-reinstall`. If the disposable demo environment is still wrong,
remove only `.java-services-demo-venv`, recreate it, reinstall both exact wheels, and repeat Step 5.
Do not delete `.venv` or unrelated environments.

### Docker or readiness failure

- Docker unavailable: start Docker Engine/Desktop and rerun Compose configuration.
- Image pull failure: verify registry access and the selected profile.
- Port occupied: use the paired port/base-URL variables in
  [Alternate ports](OPERATIONS.md#alternate-ports) before startup.
- Readiness failure: capture project-scoped `ps --all` and logs before cleanup.
- Image identity reports zero containers: confirm the same `$project`/`$compose_project` value was
  used for `up` and `verify`, and confirm the installed demo passed the CLI/import preflight.

## Validate the demo

Ordinary tests do not contact Docker or Java services. Live tests require an already running healthy
project and the explicit live-test opt-in flag shown below.

```powershell
& .\.venv\Scripts\python.exe -m pytest -c .\examples\java-services-demo\pyproject.toml .\examples\java-services-demo\tests --collect-only
& .\.venv\Scripts\python.exe -m pytest -c .\examples\java-services-demo\pyproject.toml .\examples\java-services-demo\tests
& .\.venv\Scripts\python.exe -m pytest -c .\examples\java-services-demo\pyproject.toml .\examples\java-services-demo\tests --run-java-services
```

```bash
.venv/bin/python -m pytest -c ./examples/java-services-demo/pyproject.toml ./examples/java-services-demo/tests
.venv/bin/python -m pytest -c ./examples/java-services-demo/pyproject.toml ./examples/java-services-demo/tests --run-java-services
```

## Educational output

Every SDK and curated-demo teaching result distinguishes purpose, input, public SDK operation,
observed result, persistence/external proof, explanation, consumer value, and status. JSON exposes
the same bounded structure without terminal formatting. A representative live step is:

```text
[INT-11] Update one element and read it back
Status: PASS
Persistence proof
  read_back_value: CIR4FUN Demo Chair updated ... fine
Summary:
  steps completed=14; expected errors demonstrated=1; blocked steps=0; skipped steps=0; unexpected failures=0
Strict verification: NOT_RUN (separate command).
```

## Next steps

- [Operations reference](OPERATIONS.md): profiles, alternate ports, diagnosis, CI, and evidence.
- [SDK usage](../../docs/usage.md): SDK-only construction and codecs.
- [Client reference](../../src/dpp_sdk/clients/README.md): public repository and registry operations.
- [Root README](../../README.md): SDK scope and installation choices.
