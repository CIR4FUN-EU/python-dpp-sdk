# Java-services demo operations reference

The [demo README](README.md) is the short consumer path: install, offline `sdk`, optional
connected `demo`, and project-scoped cleanup. This document owns profiles, advanced lifecycle,
maintainer verification, CI/release evidence, and diagnosis.

**Run from:** the repository root—the directory containing the root `pyproject.toml`.

## Profiles and evidence

| Profile | Use | Status |
|---|---|---|
| `.env` | Your ignored local project name, ports, and current `0.5.1` images | Default after copying `.env.example` |
| `0.5.1.env` | Current default semantic-version images | Maintained |
| `pinned.env` | Previous reproducible tag-plus-digest evidence | Historical |
| `0.5.0.env` | Previous semantic-version evidence | Historical |
| `0.4.0.env` | Legacy compatibility evidence; requires `--legacy` | Informational |

Copy `.env.example` to `.env` first, then set `COMPOSE_PROJECT_NAME` and paired host ports/base
URLs there. The lifecycle script uses `.env` by default; select a committed profile explicitly with
`$envFile` or `env_file` when needed. A missing profile is a configuration failure; it is not silently
replaced.

`demo` is the small live educational journey. Maintainers use
`python -m dpp_java_services_demo.maintainer sdk-contracts`, `live`, and `verify` for the exhaustive
SDK, service, package, image, and policy evidence. `full`, `verify`, `integration`, `services`, and
`all` remain compatibility commands. Pass the startup project with `--compose-project` so strict
image inspection targets the same isolated stack. Passing an educational step is evidence for that
step, not a compatibility certification.

## Alternate ports

Change each container port together with its public base URL in `.env` before `config`, `pull`, or `up`.

PowerShell:

```powershell
$env:DPP_REPO_PORT = "18080"
$env:DPP_REGISTRY_PORT = "18081"
$env:MOCK_REPO_PORT = "18080"
$env:MOCK_REGISTRY_PORT = "18081"
$env:DPP_REPO_BASE_URL = "http://localhost:18080"
$env:DPP_REGISTRY_BASE_URL = "http://localhost:18081"
```

Linux/macOS:

```bash
export DPP_REPO_PORT=18080
export DPP_REGISTRY_PORT=18081
export MOCK_REPO_PORT=18080
export MOCK_REGISTRY_PORT=18081
export DPP_REPO_BASE_URL=http://localhost:18080
export DPP_REGISTRY_BASE_URL=http://localhost:18081
```

Use different free ports when `18080` or `18081` is occupied.

## Project-scoped diagnosis

Never diagnose or clean up by an ambiguous default Compose project. Reuse the exact project,
Compose file, and environment file from startup.

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

Common failure branches:

- Docker unavailable: start Docker Engine/Desktop.
- Pull rejected: verify access to the image registry and selected profile.
- Port collision: set all paired port/base-URL variables above, then recreate the project.
- Readiness blocked: preserve `ps` and logs before teardown.
- `demo` or `full` missing from help: force-reinstall the exact newly built SDK and demo wheels.
- Package provenance mismatch: rebuild and force-reinstall the SDK wheel passed with `--sdk-wheel`.
- Image identity finds no container: verify `up` and `verify` used the same project name and that the
  installed demo package is current.

## Cleanup choices

The commands below affect only the named demo project. Do not substitute a shared project name.

Stop/remove containers and the project network while keeping database volumes:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile down --remove-orphans
```

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" down --remove-orphans
```

Stop/remove the project and permanently delete its disposable database volumes:

```powershell
docker compose -f $composeFile -p $project --env-file $envFile down --volumes --remove-orphans
Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue
```

```bash
docker compose -f "$compose_file" -p "$project" --env-file "$env_file" down --volumes --remove-orphans
rm -f "$report"
```

Copy a report elsewhere before removing `$report` or `"$report"` when evidence must be retained.

## Legacy profile

The `0.4.0.env` profile requires explicit `--legacy` on demo commands. Legacy runs are informational
and do not satisfy the maintained strict-verification gate. Keep their reports separate from current
`0.5.1.env` evidence.

## CI and reports

The manually triggered GitHub workflow `Java services demo verification` builds both wheels, starts
a fresh disposable stack for the selected profile, runs installed-wheel verification, captures
evidence, and tears down its project. The PyPI release workflow does not start Java images; it runs
SDK-only installed-wheel verification.

Reports distinguish `PASSED`, `EXPECTED_ERROR`, `SKIPPED`, `FAILED`, and `NOT_IMPLEMENTED`. The live
educational report uses `PASS`, `EXPECTED_ERROR`, `BLOCKED`, `SKIP`, and `FAIL`. Keep educational
success separate from the strict verification verdict.
