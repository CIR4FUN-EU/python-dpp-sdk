# Changelog

All notable changes to `dpp-sdk` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A fresh-installed-wheel cross-component proof covering validated immutable updates,
  DPP4Fun codec round-trips, captured repository/registry requests, and client error
  translation without source-tree imports.
- Python-only local-endpoint helpers and factories, with explicit `base_url` and
  environment overrides (`DPP_REPO_BASE_URL` / `DPP_REGISTRY_BASE_URL`). They do
  not provide or operate any service.
- `health_check()` on both clients (probes `GET /health`).
- Default endpoint constants and helpers exported from `dpp_sdk.clients`:
  `DEFAULT_REPO_BASE_URL`, `DEFAULT_REGISTRY_BASE_URL`, `DEFAULT_REPO_PORT`,
  `DEFAULT_REGISTRY_PORT`, `local_repo_base_url()`, `local_registry_base_url()`.
- `integration` pytest marker and opt-in live conformance tests for an
  externally supplied endpoint.

### Fixed
- Bill-of-materials validation now rejects null material, component, and part members
  with fail-fast indexed `DppValidationError` paths instead of leaking `AttributeError`.
- History reads now normalize timezone-aware datetimes to the Java-compatible canonical UTC
  `Z` query wire, including Java-compatible fractional-second precision.
- Repository identifiers and element paths now use exact dynamic-segment percent encoding,
  preserving literal `*` while encoding `~`, `%`, `?`, and `#`.
- Repository and registry clients now reject null response payloads, null codec results, and
  invalid registry requests through causal `DppMappingClientError` failures before invalid
  values or raw implementation exceptions can escape.
- Contracted text fields use an explicit frozen Unicode White_Space table in construction,
  semantic validation, duplicate comparison, and cross-object comparison.
- Contracted floating-point values are finite and non-negative; strict JSON mapping rejects
  non-finite input, overflow, and output with preserved causes.
- Standalone codec roots and null string-list members follow the approved structural mapping
  boundary, while direct defensive validators retain indexed semantic errors.

### Changed
- Active model guidance and contract tests consistently use `with_updates()` as the
  revalidating immutable-edit seam; intentional Pydantic bypass probes remain internal.
- `README.md`: full lifecycle Quickstart (build → validate → store → register → read → update →
  delete) now uses application-provided endpoints and no-network examples.

### Changed
- Domain models expose `with_updates()` for revalidated immutable updates; contracted collections
  are immutable tuples in memory and continue to serialize as JSON arrays.
- Validation documentation now describes the tested fail-fast behavior rather than aggregation.
- Canonical repository and registry documentation uses `/v1` routes, canonical registration
  fields and `registrationId`, compressed/versioned reads, direct data-element JSON bodies, and
  distinct client error categories.
- Both SDK clients support explicit `close()` and context-manager cleanup for SDK-owned HTTPX
  resources; caller-supplied clients remain caller-owned.
- Aggregate validators document and test their supported public boundary and fail-fast order;
  arbitrary `model_construct()` corruption is not a public compatibility contract.

### Compatibility
- `UpdateDataElementRequest` remains importable only as a compatibility DTO; it does not affect
  canonical direct data-element PATCH bodies.
- Legacy registry aliases and the unversioned product-ID history route are retained compatibility
  surfaces only. New integrations should use canonical field names and versioned routes.

## [0.2.1] — Current package baseline

- Package metadata and `dpp_sdk.__version__` identify this checkout as `0.2.1`.
- This repository checkout contains no local release tag for `0.2.1`; commit history remains
  the provenance source for changes predating the current unreleased section.

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
