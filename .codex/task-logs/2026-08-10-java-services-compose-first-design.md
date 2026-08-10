# Java-services Compose-first README design

## Goal

Make the Java-services demo startup instructions usable on Windows systems that block PowerShell scripts, without changing the Java services or their lifecycle behavior.

## Scope

- Make native Docker Compose the primary Step 8 startup path in `examples/java-services-demo/README.md`.
- State that Docker Engine or Docker Desktop must be running before startup.
- Retain `manage-java-services.ps1` as an explicitly optional convenience wrapper.
- Add static regression coverage that protects this ordering and wording.

## Non-goals

- No new launcher, Docker configuration, service behavior, image, port, cleanup, or execution-policy changes.
- No changes outside the demo README and its focused regression test.

## Design

Step 8 will first run the existing project-scoped `docker compose config`, `pull`, and `up --wait` commands, followed by both configured `/health` requests. The PowerShell lifecycle wrapper will follow in a short optional subsection for systems that permit `.ps1` execution. The existing project and environment variables remain the sole inputs to both paths.

## Validation

Run the focused demo script regression test, verify the documentation references and command ordering, inspect the final diff, and run `git diff --check`.
