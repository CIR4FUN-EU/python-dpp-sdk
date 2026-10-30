# Mock-services demo

This demo shows the Python SDK at work in two steps:

1. **Offline walkthrough:** five SDK scenarios that need no services and no Docker.
2. **Connected demo:** the SDK talks to example Java repository and registry services that run
   locally in Docker. The service images are set in [compose.yaml](compose.yaml).

The demo is optional and separate from the SDK. You don't need it to use `dpp-sdk`.

## Before you start

- Python 3.11 or newer.
- For the connected demo only: [Docker](https://docs.docker.com/get-started/get-docker/) with
  Compose v2 (on Windows and macOS: Docker Desktop, started).
- A clone of this repository with an activated development environment. See
  [Set up the development environment](../../CONTRIBUTING.md#set-up-the-development-environment).

**Run from:** the repository root (the folder that contains `pyproject.toml`) for every command
on this page.

## Quick start

Install the demo and run the offline walkthrough. The offline example does not load a service
profile or contact Docker:

```bash
python -m pip install -e ./examples/mock-services-demo
python -m dpp_mock_services_demo sdk
```

To see the SDK calls behind each scenario, read the commented
[sdk_scenarios.py](src/dpp_mock_services_demo/sdk_scenarios.py).

## Optional connected demo

First check that Docker is running:

```bash
docker compose version
```

You should see a version number. If you see an error, start Docker Desktop (or Docker Engine) first.

The commands below:

1. create your local settings file `.env` from `.env.example`, if it doesn't exist yet. It sets
   the ports, 18080 for the repository and 18081 for the registry (the README quickstart runs
   without `.env` and uses 8080 and 8081, so both can run side by side);
2. start the services;
3. run the demo;
4. stop the services.

Every command uses the same project name, so cleanup only affects this demo (project-scoped).

### PowerShell

```powershell
$demoDir = (Resolve-Path .\examples\mock-services-demo).Path
$envFile = Join-Path $demoDir ".env"
$composeFile = Join-Path $demoDir "compose.yaml"
$project = "dpp-mock-services-demo-local"
if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item (Join-Path $demoDir ".env.example") $envFile }

docker compose --env-file $envFile -f $composeFile -p $project pull
docker compose --env-file $envFile -f $composeFile -p $project up -d --wait
python -m dpp_mock_services_demo demo --env-file $envFile
docker compose --env-file $envFile -f $composeFile -p $project down
```

### Bash (Linux/macOS)

```bash
demo_dir="$(cd ./examples/mock-services-demo && pwd)"
env_file="$demo_dir/.env"
compose_file="$demo_dir/compose.yaml"
project="dpp-mock-services-demo-local"
[ -f "$env_file" ] || cp "$demo_dir/.env.example" "$env_file"

docker compose --env-file "$env_file" -f "$compose_file" -p "$project" pull
docker compose --env-file "$env_file" -f "$compose_file" -p "$project" up -d --wait
python -m dpp_mock_services_demo demo --env-file "$env_file"
docker compose --env-file "$env_file" -f "$compose_file" -p "$project" down
```

`down` stops the services but keeps their stored data. To delete the data too, add `--volumes`.

To see the client calls and the cleanup order, read the commented
[integration_scenarios.py](src/dpp_mock_services_demo/integration_scenarios.py).

## If something goes wrong

- **Port already in use:** change the ports in `.env`. See
  [alternate ports](ADVANCED_OPERATIONS.md#alternate-ports).
- **`docker compose up` fails or hangs:** see
  [project-scoped diagnosis](ADVANCED_OPERATIONS.md#project-scoped-diagnosis).

For logs, other service versions, and maintainer verification, see
[ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md).
