# Contributing

This page is for people working on the SDK itself. To use the SDK, start with the
[README](README.md).

## Set up the development environment

**Run from:** the repository root (the folder that contains `pyproject.toml`).

```bash
git clone https://github.com/CIR4FUN-EU/python-dpp-sdk.git
cd python-dpp-sdk
python -m venv .venv
```

Activate the environment. Do this once in every new terminal:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`. If PowerShell blocks it, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- Linux/macOS: `source .venv/bin/activate`. If `python` is not found, use `python3`.

Then install the SDK with its development tools and run the tests:

```bash
python -m pip install -e ".[dev,release]"
python -m pytest
```

## Checks

Run these before you open a pull request. CI runs the same commands on Python 3.11 and 3.12.

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

Focused test sets, all without running services (the clients tests use `httpx.MockTransport`):

| Area | Command |
| --- | --- |
| Core model and validation | `python -m pytest tests/test_core_model.py tests/test_core_json_codec.py tests/test_core_validation_parity.py` |
| DPP4Fun profile | `python -m pytest tests/test_dpp4fun_validation.py tests/test_transport_roundtrip.py` |
| HTTP clients | `python -m pytest tests/test_clients.py tests/test_end_to_end.py` |
| Documentation | `python -m pytest tests/test_documentation.py tests/test_readme_examples.py` |

Live tests against running services are opt-in; see
[ADVANCED_OPERATIONS.md](examples/mock-services-demo/ADVANCED_OPERATIONS.md).

## Documentation

- `README.md` is also the PyPI project page. Use absolute `https://` links there; PyPI cannot
  resolve relative links.
- The README and guides contain no version numbers; a test enforces this.
- The Python code blocks in `README.md`, `docs/model-guide.md`, and `docs/extending.md` are executed
  by the documentation tests. Keep them runnable.
- `docs/dpp4fun-fields.md` is generated. After changing the DPP4Fun semantic profile, regenerate it:

  ```bash
  python scripts/generate_dpp4fun_fields.py
  ```

  A test fails when the committed file is out of date.

## Architecture diagrams

Each maintained consumer diagram has an editable Mermaid source and a sibling SVG preview under
`docs/architecture/`. The render script uses the pinned Mermaid CLI image
`ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:11.4.2` (digest
`sha256:99c983b3ab4e14033f2880bc1b9de17e5090b4515dabd63fe9cf8c0ae6130956`). Docker must be able to
pull that image before rendering.

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1
powershell -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1 -VerifyOnly
```

```bash
pwsh -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1
pwsh -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1 -VerifyOnly
```

`-VerifyOnly` checks that each source has an SVG and does not render or modify assets. Review SVG
diffs after rendering. The published diagram pairs are:

| Diagram | Mermaid source | SVG preview |
|---|---|---|
| SDK overview | [python-sdk-overview.mmd](docs/architecture/python-sdk-overview.mmd) | [python-sdk-overview.svg](docs/architecture/python-sdk-overview.svg) |
| Client request flow | [python-client-request-flow.mmd](docs/architecture/python-client-request-flow.mmd) | [python-client-request-flow.svg](docs/architecture/python-client-request-flow.svg) |
| Core model | [python-core-model.mmd](docs/architecture/python-core-model.mmd) | [python-core-model.svg](docs/architecture/python-core-model.svg) |
| DPP4Fun model | [python-dpp4fun-model.mmd](docs/architecture/python-dpp4fun-model.mmd) | [python-dpp4fun-model.svg](docs/architecture/python-dpp4fun-model.svg) |

## Mock-service verification

Commands are in [ADVANCED_OPERATIONS.md](examples/mock-services-demo/ADVANCED_OPERATIONS.md).
This section records what the profiles and reports mean.

| Profile (`examples/mock-services-demo/`) | Use | Status |
|---|---|---|
| `compose.yaml` defaults or `.env` | Local consumer profile with the current example Java images | Primary |
| `env/0.5.1.env` | Image-identity verification profile, also the CI default | Maintained |
| `env/pinned.env` | Earlier reproducible tag-plus-digest evidence | Historical |
| `env/0.5.0.env` | Earlier semantic-version evidence | Historical |
| `env/0.4.0.env` | Legacy compatibility evidence; demo commands need `--legacy` | Informational |

Legacy runs are informational and do not satisfy the strict verification gate. Keep their reports
separate from the maintained profile's evidence.

`demo` is the short educational journey. `python -m dpp_mock_services_demo.maintainer
sdk-contracts`, `live`, and `verify` produce the full SDK, service, package, image, and policy
evidence. `full`, `verify`, `integration`, `services`, and `all` remain compatibility commands.
Passing an educational step is evidence for that step only, not a compatibility certification.

The manually triggered GitHub workflow `Mock services demo verification` builds both wheels, starts
a fresh disposable stack for the selected profile, runs installed-wheel verification, captures
evidence, and tears down its project. The PyPI release workflow does not start mock images; it runs
SDK-only installed-wheel verification.

Strict reports use `PASSED`, `EXPECTED_ERROR`, `SKIPPED`, `FAILED`, and `NOT_IMPLEMENTED`. The
educational report uses `PASS`, `EXPECTED_ERROR`, `BLOCKED`, `SKIP`, and `FAIL`. Keep educational
success separate from the strict verification verdict. Clean up reports separately from Compose
projects, and keep the ones you need as evidence.

## Releasing

The release steps are in [RELEASING.md](RELEASING.md).
