# Releasing `dpp-sdk`

This project ships a single PyPI package, `dpp-sdk`, built with
[hatchling](https://hatch.pypa.io/). Releases are automated with GitHub Actions and
**PyPI Trusted Publishing** (OIDC) — no API tokens are ever stored.

- Build tool: `python -m build` → `dist/dpp_sdk-X.Y.Z-py3-none-any.whl` + `.tar.gz`
- Version source of truth: `__version__` in `src/dpp_sdk/__init__.py`
  (hatchling reads it via `[tool.hatch.version]`)
- Workflows: `.github/workflows/release.yml` (publish) and `ci.yml` (test gate)

---

## One-time setup (do this once, before the first release)

Trusted Publishing maps a specific GitHub repo + workflow + environment to a PyPI project.
It must be registered **before** the first upload, while the project name is still unclaimed
(a "pending publisher").

### 1. Create accounts
- PyPI: <https://pypi.org/account/register/>
- TestPyPI (separate account): <https://test.pypi.org/account/register/>

Enable 2FA on both.

### 2. Register the pending publisher on **PyPI**
Go to <https://pypi.org/manage/account/publishing/> → "Add a new pending publisher" and enter:

| Field | Value |
|---|---|
| PyPI Project Name | `dpp-sdk` |
| Owner | `CIR4FUN-EU` |
| Repository name | `dpp-sdk-python` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

### 3. Register the pending publisher on **TestPyPI**
Repeat at <https://test.pypi.org/manage/account/publishing/> with the **same values**, except:

| Field | Value |
|---|---|
| Environment name | `testpypi` |

### 4. Create the GitHub Environments
In the GitHub repo → Settings → Environments, create two environments whose names match
the workflow:
- `testpypi`
- `pypi` — add yourself (`OnneM156`) as a **Required reviewer** so production uploads pause
  for manual approval.

No secrets are needed in either environment; OIDC handles auth.

---

## Cutting a release

1. Make sure `main` is green (CI passes: ruff, mypy, pytest).
2. Bump the version in `src/dpp_sdk/__init__.py` (`__version__ = "X.Y.Z"`), following
   [SemVer](https://semver.org/).
3. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z]` heading and
   update the compare links at the bottom.
4. Commit: `git commit -am "Release vX.Y.Z"` and push to `main`.
5. Tag and push the tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
6. The **Release** workflow runs automatically:
   - builds the sdist + wheel and runs `twine check`,
   - publishes to **TestPyPI**,
   - then waits on the `pypi` environment for your approval.
7. Verify the TestPyPI artifact in a clean environment:
   ```bash
   python -m venv /tmp/relcheck && source /tmp/relcheck/bin/activate
   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ dpp-sdk
   python -c "import dpp_sdk; print(dpp_sdk.__version__)"
   ```
   (The `--extra-index-url` lets `pydantic`/`httpx` resolve from real PyPI, since TestPyPI
   may not host them.)
8. Approve the `pypi` environment in the GitHub Actions run → the package publishes to PyPI.
9. Confirm:
   ```bash
   pip install dpp-sdk
   python -c "import dpp_sdk; from dpp_sdk import Dpp4Fun; print(dpp_sdk.__version__)"
   ```

> **Note:** a given version can only be uploaded once. If a (Test)PyPI upload of `X.Y.Z`
> already exists, bump to a new version — you cannot overwrite or re-upload it.

---

## Manual fallback (no CI)

If you ever need to publish from a workstation instead of CI:

```bash
pip install -e ".[release]"        # installs build + twine
python -m build                     # -> dist/
twine check dist/*
twine upload --repository testpypi dist/*   # dry run
twine upload dist/*                          # real PyPI
```

This uses a PyPI API token configured in `~/.pypirc` rather than Trusted Publishing.
Prefer the tag-driven CI flow above whenever possible.
