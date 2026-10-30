# Release guide

This repository publishes the `dpp-sdk` Python package from version tags matching
`v<major>.<minor>.<patch>`.

## Version bump checklist

The SDK version appears in these places only. Update all of them together:

- `src/dpp_sdk/__init__.py` (`__version__`, the single source for the package build)
- `CHANGELOG.md` (move `[Unreleased]` entries under the new version, add the release date, and
  add a compare link for the new version at the bottom)
- `examples/mock-services-demo/pyproject.toml` (the `dpp-sdk==` pin)
- `.github/workflows/mock-services-demo.yml` (the `dpp_sdk-<version>-py3-none-any.whl` file name)
- `tests/test_release_validation.py` (the expected package version)

The example Java service version appears only in `examples/mock-services-demo/compose.yaml` and
`examples/mock-services-demo/.env.example` (the image tags).

The README and guides deliberately contain no version numbers, and a test enforces this.

## Before tagging

**Run from:** the Python repository root, the directory containing `pyproject.toml`.
**Prerequisites:** the development environment from [CONTRIBUTING.md](CONTRIBUTING.md), activated.

1. Work through the version bump checklist above.
2. Run the configured validation. The commands are the same in PowerShell and Bash:

   ```bash
   python -c "from dpp_sdk import __version__; print(__version__)"
   python -m ruff check .
   python -m ruff format --check .
   python -m mypy
   python -m pytest
   ```

   The first command prints the version you are about to release.

3. Build, check, and inspect the packages and verify a fresh installation without source-tree
   imports. Use the [disposable build](#disposable-build-and-archive-inspection) below; it never
   touches `dist/`.
4. Confirm the repository is clean and review the release diff.

## Disposable build and archive inspection

Use a temporary directory so release checks never overwrite a pre-existing `dist/` directory.
These commands run from the Python repository root and work when that path contains spaces.

PowerShell:

```powershell
$runId = [guid]::NewGuid().ToString("N")
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-sdk-release-$runId"
$testEnv = Join-Path ([System.IO.Path]::GetTempPath()) "dpp-sdk-wheel-$runId"
if ((Test-Path -LiteralPath $buildRoot) -or (Test-Path -LiteralPath $testEnv)) { throw "Temporary path already exists; choose a new run ID." }
New-Item -ItemType Directory -Path $buildRoot, $testEnv | Out-Null
python -m build --outdir $buildRoot
python -m twine check "$buildRoot\*"
Get-ChildItem $buildRoot
python -m zipfile -l (Get-ChildItem "$buildRoot\*.whl").FullName
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
import_root="$(mktemp -d)"
python -m build --outdir "$build_root"
python -m twine check "$build_root"/*
ls -la "$build_root"
python -m zipfile -l "$(find "$build_root" -maxdepth 1 -name '*.whl' -print -quit)"
python -m venv "$test_env"
"$test_env/bin/python" -m pip install "$(find "$build_root" -maxdepth 1 -name '*.whl' -print -quit)"
(cd "$import_root" && "$test_env/bin/python" -I -c 'import dpp_sdk; print(dpp_sdk.__version__)')
rm -rf "$test_env" "$build_root" "$import_root"
```

Expected result: build and Twine succeed, the wheel lists only intended package files, and the
fresh interpreter imports `dpp_sdk` outside the checkout. If build tooling is missing, recreate the
development environment from [CONTRIBUTING.md](CONTRIBUTING.md). Keep the temporary directories when a command fails so
their artifacts can be inspected; remove only directories created by this sequence after review.

## Publishing

Pushing a version tag starts `.github/workflows/release.yml`. The workflow builds the
sdist and wheel, checks metadata and README rendering, publishes first to TestPyPI, and
then uses the protected `pypi` environment for production publication.

Run these from the repository root, in order, after the release changes are merged into
the default branch on GitHub. Replace `X.Y.Z` with the version from `src/dpp_sdk/__init__.py`.
The git commands are the same in PowerShell and Bash:

```bash
# 1. Get the merged release commit onto the default branch locally.
git checkout main
git pull https://github.com/CIR4FUN-EU/python-dpp-sdk.git main

# 2. Tag that commit with the version.
git tag vX.Y.Z

# 3. Push the tag to GitHub to start the release workflow.
git push https://github.com/CIR4FUN-EU/python-dpp-sdk.git vX.Y.Z
```

The tag must point at a commit already on GitHub's default branch, and its name must match
the intended version. Once the tag is pushed, the workflow runs automatically — no further
commands are needed. Do not delete or move a tag after the workflow has published it.

Both package indexes must configure this repository's GitHub Actions workflow as an
OIDC Trusted Publisher. No API token belongs in the repository.

Publishing configuration proves only the release mechanism. It does not establish
standards compliance, certification, or external-service readiness.
