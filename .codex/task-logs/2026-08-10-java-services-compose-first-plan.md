# Java-services Compose-first README Implementation Plan

**Goal:** Make Docker Compose the primary Java-services startup path so Windows PowerShell policy does not block the demo.

**Architecture:** Keep the existing Compose commands and lifecycle script unchanged. Reorder only the README guidance, with the direct Compose path first and the PowerShell script explicitly optional; protect that documentation contract with the existing static regression test.

**Tech Stack:** Markdown, pytest, Docker Compose command documentation.

## Global Constraints

- Preserve project-scoped Compose arguments, `.env` inputs, health checks, and all service behavior.
- Do not add launchers, dependencies, Docker configuration, or execution-policy changes.
- Keep Docker Engine/Desktop as an explicit prerequisite for live modes.

### Task 1: Make Compose startup the primary documented route

**Files:**
- Modify: `examples/java-services-demo/README.md`
- Modify: `examples/java-services-demo/tests/test_manage_services_script.py`

**Interfaces:**
- Consumes: `$composeFile`, `$project`, `$envFile`, `DPP_REPO_BASE_URL`, and `DPP_REGISTRY_BASE_URL` established in Step 7.
- Produces: Copyable project-scoped Compose startup guidance and an optional `manage-java-services.ps1` convenience invocation.

- [x] **Step 1: Write the failing static regression test**

```python
assert "Docker Engine or Docker Desktop must be running" in guide
assert guide.index("docker compose -f $composeFile -p $project --env-file $envFile config --quiet") < guide.index("& $serviceScript -Action Start -EnvFile $envFile")
assert "Optional PowerShell convenience wrapper" in guide
```

- [x] **Step 2: Run the focused test to verify it fails for the missing documentation contract**

Run: `& .\\.venv\\Scripts\\python.exe -m pytest -c .\\examples\\java-services-demo\\pyproject.toml .\\examples\\java-services-demo\\tests\\test_manage_services_script.py -q`

Expected: failure because the README still presents the PowerShell invocation before the native Compose commands.

- [x] **Step 3: Make the minimum README change**

Replace the Step 8 primary PowerShell invocation with the existing `config --quiet`, `pull --policy missing`, `up -d --wait --wait-timeout 120`, and two `Invoke-RestMethod` commands. Add one sentence requiring Docker Engine/Desktop to be running. Put the unchanged `& $serviceScript -Action Start -EnvFile $envFile` under an `Optional PowerShell convenience wrapper` subsection.

- [x] **Step 4: Run focused validation and documentation checks**

Run: `& .\\.venv\\Scripts\\python.exe -m pytest -c .\\examples\\java-services-demo\\pyproject.toml .\\examples\\java-services-demo\\tests\\test_manage_services_script.py -q`

Run: `git diff --check`

Expected: test passes and diff check returns no output.

- [x] **Step 5: Review and commit the bounded change**

Inspect `git diff -- README.md tests/test_manage_services_script.py` and confirm that no lifecycle behavior changed. Stage the README, test, and retained plan/log records, then commit with `docs: lead Java demo startup with Compose`.

## Self-review

- Spec coverage: Task 1 covers Compose-first ordering, Docker prerequisite wording, optional wrapper labeling, and regression coverage.
- Placeholder scan: no placeholders or deferred steps remain.
- Scope check: the task changes one documentation flow and its focused static regression check; no subsystem split is needed.
