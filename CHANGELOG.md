# Changelog

All notable changes to `dpp-sdk` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `DppRepoClient.for_local_mock()` and `DppRegistryClient.for_local_mock()` factories that
  point the clients at the local mock services (`http://localhost:8080` / `:8081`), with an
  optional `base_url` override and env overrides (`DPP_REPO_PORT` / `DPP_REGISTRY_PORT`, or
  the full `DPP_REPO_BASE_URL` / `DPP_REGISTRY_BASE_URL`).
- `health_check()` on both clients (probes `GET /health`).
- Default endpoint constants and helpers exported from `dpp_sdk.clients`:
  `DEFAULT_REPO_BASE_URL`, `DEFAULT_REGISTRY_BASE_URL`, `DEFAULT_REPO_PORT`,
  `DEFAULT_REGISTRY_PORT`, `local_repo_base_url()`, `local_registry_base_url()`.
- `integration` pytest marker and a live conformance test suite (`tests/test_integration_live.py`)
  that exercises the clients against the running mock services and auto-skips when they are down.

### Changed
- `README.md`: full lifecycle Quickstart (build → validate → store → register → read → update →
  delete) and a guide for integration-testing against the mock services.

## [0.1.1]

### Changed
- Documentation update: streamlined `README.md` and project metadata.

## [0.1.0] — Initial release

First public release of the Python port of the Java DPP SDK.

### Added
- `dpp_sdk.core` — core DPP model, validation, and identifiers (Pydantic v2).
- `dpp_sdk.dpp4fun` — furniture-specific DPP aggregate, validation, and flat/nested JSON transport.
- `dpp_sdk.clients` — `httpx`-based HTTP clients for the DPP repository and registry APIs.
- Packaging: PEP 621 `pyproject.toml`, `src/` layout, `py.typed` marker, sdist + wheel build.

[Unreleased]: https://github.com/CIR4FUN-EU/dpp-sdk-python/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/CIR4FUN-EU/dpp-sdk-python/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/CIR4FUN-EU/dpp-sdk-python/releases/tag/v0.1.0
