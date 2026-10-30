# Changelog

All notable changes to `dpp-sdk` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-10-30


### Added
- A canonical `DigitalProductPassport` model with a `DppHeader` and typed DataElement variants,
  plus FULL and COMPRESSED JSON codecs and explicit semantic, format, and identifier validation.
- A typed DPP4Fun profile over the core passport, including its bundled 488-definition semantic catalog,
  typed aspects and Characteristics variants, reusable composites, profile validation, and transport codec.
- Generic JSON repository and registry clients that accept JSON-compatible request values and return
  response envelopes without owning domain codecs or validation.

### Changed
- The core model and furniture profile now use the final passport structure and current profile
  semantics; the earlier `Dpp`/`DppCore` and flat furniture model shapes are no longer accepted as
  current model APIs.
- Client methods return neutral response DTOs. Repository payloads are exposed through
  `DppApiResponse.payload`; clients do not parse them into caller-selected model types.
- Public model and client attributes use Python `snake_case` while JSON aliases retain the API's
  canonical field names.
- Repository and registry clients require explicit service base URLs. Callers own model parsing,
  serialization, and validation.

### Fixed
- Reject malformed HTTP base URLs before sending a request, and require `messageType` and `text`
  for each API message while allowing the outer `message` list to be absent or empty.
- Preserve numeric DataElement equality and hashing across nested integer, float, and Decimal values.
- Apply the approved DPP4Fun profile bindings, unit handling, and semantic-resolution behavior.

### Documentation
- Added a generated DPP4Fun field reference, a guide for building your own profile on Core, a
  standards and validation-rules page, and a contributing guide.
- Reorganized the model guide around tasks (build, read, edit, validate, convert) and documented
  the read API (`typed_aspect()`, `field()`, `quantity()`, `selected_characteristics()`).
- The README quickstart now reads the passport back as a typed object and lists the exceptions.

### Breaking changes and migration

The released `v0.4.0` repository client accepted a model codec and validator and returned typed model
objects. The `0.5.0` client takes only a service URL (and optionally a caller-supplied HTTPX client),
accepts JSON-compatible values, and returns response envelopes. Move validation and codec work to the
application boundary:

```python
# v0.4.0
repo = DppRepoClient(base_url, codec, validate_dpp4fun)
created = repo.create_dpp(passport)
loaded = repo.read_dpp_by_id(created.dppId)

# 0.5.0
import json
from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppRepresentation, DppRepoClient

codec = Dpp4FunJsonCodec()
validation = validate_dpp4fun(passport)
if not validation.is_valid:
    raise ValueError(validation.issues)
with DppRepoClient(base_url) as repo:
    created = repo.create_dpp(json.loads(codec.to_json(passport)))
    if created.digital_product_passport_id is None:
        raise RuntimeError("repository did not return a passport ID")
    response = repo.read_dpp_by_id(
        created.digital_product_passport_id,
        DppRepresentation.FULL,
    )
    loaded = codec.from_json(json.dumps(response.payload))
```

`DppApiResponse` carries `status_code`, `payload`, and `message`. API failures raise
`DppApiClientError`; malformed JSON or payload mapping raises `DppMappingClientError`; unstructured
HTTP failures and transport failures use `DppHttpClientError` and `DppNetworkClientError`. Semantic
validation is performed explicitly before a request with the relevant core or DPP4Fun validator.

The former `Dpp`/`DppCore` model family and flat furniture classes were replaced by
`DigitalProductPassport`, `DppHeader`, five DataElement variants, and a DPP4Fun aggregate over the
canonical passport. Python object attributes also changed from camelCase to `snake_case`; for
example, `dpp.passportMetadata.uniqueProductIdentifier` is now
`passport.dpp_header.unique_product_identifier`, while the JSON key remains
`uniqueProductIdentifier`. Map stored legacy fields to the current model explicitly; no general
legacy model converter is provided. Use `DppJsonCodec.to_expanded_json()` or
`DppJsonCodec.to_compressed_json()` for core transport, and `Dpp4FunJsonCodec` for typed profile
views. FULL responses can be decoded with the codec; COMPRESSED responses may need prior metadata or
semantic resolution to restore typed details.

The `for_local_mock()` factories, default endpoint helpers/constants, `health_check()`, typed
`read_compressed_dpp_by_id()`, product-ID historical-read helper, the `dpp_sdk.clients.DppCodec`
and `dpp_sdk.clients.DppValidator` typing protocols, `DppValidationClientError`, and the
`UpdateDataElementRequest` compatibility DTO are not part of the current client API. (The model
validator `dpp_sdk.core.DppValidator` is unaffected.) Pass local service URLs directly, check service health independently, use
`read_dpp_version_by_id_and_date()` for supported history reads, and pass direct JSON-compatible
DataElement bodies to fine-grained update methods.

### Compatibility
- The generic JSON client API is a breaking change from the released typed-client API; see the
  migration examples above.
- The legacy product-ID history route and legacy registry request aliases are not part of the
  current public Python client surface.

## [0.4.0] - 2026-08-11

### Added
- An isolated `examples/mock-services-demo` consumer project with reproducible Mock image
  profiles, pull-only memory-mode Compose infrastructure, SDK-01 through SDK-17, complete public
  repository/registry interoperability scenarios, controlled edge contracts, installed-import
  proof, dynamic image identity evidence, and retained verification reports.
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
- The installed Mock-services demo's SDK-only modes now defer service-profile loading, so `sdk`
  and `sdk --json` run from an installed nested wheel without a checkout or `env/pinned.env`.
- Mock-services demo configuration tests now isolate service environment variables, so documented
  alternate host-port overrides cannot contaminate profile/default assertions.
- Bill-of-materials validation now rejects null material, component, and part members
  with fail-fast indexed `DppValidationError` paths instead of leaking `AttributeError`.
- History reads now normalize timezone-aware datetimes to the Mock-compatible canonical UTC
  `Z` query wire, including Mock-compatible fractional-second precision.
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
- `README.md`: full lifecycle Quickstart (build → validate → store → register → read → update →
  delete) now uses application-provided endpoints and no-network examples.
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
- Root and module READMEs now use plain-language entry points, explain Python client payload models,
  distinguish optional Mock-demo prerequisites, and include focused Mermaid diagrams with captions.

### Compatibility
- `UpdateDataElementRequest` remains importable only as a compatibility DTO; it does not affect
  canonical direct data-element PATCH bodies.
- Legacy registry aliases and the unversioned product-ID history route are retained compatibility
  surfaces only. New integrations should use canonical field names and versioned routes.

## [0.2.1] — Previous package baseline

- Package metadata and `dpp_sdk.__version__` identified version `0.2.1`.
- Commit history remains the provenance source for changes predating the `0.2.1` baseline.

## [0.1.1]

### Changed
- Documentation update: streamlined `README.md` and project metadata.

## [0.1.0] — Initial release

First public release of the Python port of the Mock DPP SDK.

### Added
- `dpp_sdk.core` — core DPP model, validation, and identifiers (Pydantic v2).
- `dpp_sdk.dpp4fun` — furniture-specific DPP aggregate, validation, and flat/nested JSON transport.
- `dpp_sdk.clients` — `httpx`-based HTTP clients for the DPP repository and registry APIs.
- Packaging: PEP 621 `pyproject.toml`, `src/` layout, `py.typed` marker, sdist + wheel build.

[Unreleased]: https://github.com/CIR4FUN-EU/python-dpp-sdk/compare/v0.5.0...main
[0.5.0]: https://github.com/CIR4FUN-EU/python-dpp-sdk/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/CIR4FUN-EU/python-dpp-sdk/compare/v0.2.1...v0.4.0
[0.2.1]: https://github.com/CIR4FUN-EU/python-dpp-sdk/compare/v0.1.1...v0.2.1
[0.1.1]: https://github.com/CIR4FUN-EU/python-dpp-sdk/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/CIR4FUN-EU/python-dpp-sdk/releases/tag/v0.1.0
