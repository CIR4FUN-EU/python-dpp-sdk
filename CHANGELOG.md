# Changelog

All notable changes to `dpp-sdk` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — Initial release

First public release of the Python port of the Java DPP SDK.

### Added
- `dpp_sdk.core` — core DPP model, validation, and identifiers (Pydantic v2).
- `dpp_sdk.dpp4fun` — furniture-specific DPP aggregate, validation, and flat/nested JSON transport.
- `dpp_sdk.clients` — `httpx`-based HTTP clients for the DPP repository and registry APIs.
- Packaging: PEP 621 `pyproject.toml`, `src/` layout, `py.typed` marker, sdist + wheel build.

[Unreleased]: https://github.com/CIR4FUN-EU/dpp-sdk-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CIR4FUN-EU/dpp-sdk-python/releases/tag/v0.1.0
