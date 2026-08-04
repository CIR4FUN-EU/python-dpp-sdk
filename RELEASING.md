# Release guide

This repository publishes the `dpp-sdk` Python package from version tags matching
`v<major>.<minor>.<patch>`.

## Before tagging

**Run from:** repository root. **Prerequisites:** the checkout development environment.

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

## Publishing

Pushing a version tag starts `.github/workflows/release.yml`. The workflow builds the
sdist and wheel, checks metadata and README rendering, publishes first to TestPyPI, and
then uses the protected `pypi` environment for production publication.

Both package indexes must configure this repository's GitHub Actions workflow as an
OIDC Trusted Publisher. No API token belongs in the repository.

Publishing configuration proves only the release mechanism. It does not establish
standards compliance, certification, or external-service readiness.
