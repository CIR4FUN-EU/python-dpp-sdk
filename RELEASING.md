# Release guide

This repository publishes the `dpp-sdk` Python package from version tags matching
`v<major>.<minor>.<patch>`.

## Before tagging

**Run from:** the Python repository root, the directory containing `pyproject.toml`.
**Prerequisites:** the checkout development environment.

1. Confirm `src/dpp_sdk/__init__.py`, `CHANGELOG.md`, and the intended tag use the same version.
2. Run the configured validation:

   ```powershell
   .\.venv\Scripts\python.exe -m ruff check .
   .\.venv\Scripts\python.exe -m ruff format --check .
   .\.venv\Scripts\python.exe -m mypy
   .\.venv\Scripts\python.exe -m pytest
   .\.venv\Scripts\python.exe -m build
   .\.venv\Scripts\python.exe -m twine check dist/*
   ```

3. Inspect the wheel and verify a fresh installation without source-tree imports.
4. Confirm the repository is clean and review the release diff.

## Disposable build and archive inspection

Use a temporary directory so release checks never overwrite a pre-existing `dist/` directory.
These commands run from the Python repository root and work when that path contains spaces.

PowerShell:

```powershell
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-sdk-release-$PID"
$testEnv = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-sdk-wheel-$PID"
New-Item -ItemType Directory -Path $buildRoot | Out-Null
.\.venv\Scripts\python.exe -m build --outdir $buildRoot
.\.venv\Scripts\python.exe -m twine check "$buildRoot\*"
Get-ChildItem $buildRoot
.\.venv\Scripts\python.exe -m zipfile -l (Get-ChildItem "$buildRoot\*.whl").FullName
python -m venv $testEnv
& "$testEnv\Scripts\python.exe" -m pip install (Get-ChildItem "$buildRoot\*.whl").FullName
Push-Location ([System.IO.Path]::GetTempPath())
try { & "$testEnv\Scripts\python.exe" -I -c "import dpp_sdk; print(dpp_sdk.__version__)" } finally { Pop-Location }
Remove-Item -Recurse -Force $testEnv, $buildRoot
```

Linux/macOS:

```bash
build_root="$(mktemp -d)"
test_env="$(mktemp -d)"
.venv/bin/python -m build --outdir "$build_root"
.venv/bin/python -m twine check "$build_root"/*
ls -la "$build_root"
.venv/bin/python -m zipfile -l "$(find "$build_root" -maxdepth 1 -name '*.whl' -print -quit)"
python -m venv "$test_env"
"$test_env/bin/python" -m pip install "$(find "$build_root" -maxdepth 1 -name '*.whl' -print -quit)"
(cd "$(mktemp -d)" && "$test_env/bin/python" -I -c 'import dpp_sdk; print(dpp_sdk.__version__)')
rm -rf "$test_env" "$build_root"
```

Expected result: build and Twine succeed, the wheel lists only intended package files, and the
fresh interpreter imports `dpp_sdk` outside the checkout. If build tooling is missing, recreate the
development environment from the README. Keep the temporary directories when a command fails so
their artifacts can be inspected; remove only directories created by this sequence after review.

## Publishing

Pushing a version tag starts `.github/workflows/release.yml`. The workflow builds the
sdist and wheel, checks metadata and README rendering, publishes first to TestPyPI, and
then uses the protected `pypi` environment for production publication.

Both package indexes must configure this repository's GitHub Actions workflow as an
OIDC Trusted Publisher. No API token belongs in the repository.

Publishing configuration proves only the release mechanism. It does not establish
standards compliance, certification, or external-service readiness.
