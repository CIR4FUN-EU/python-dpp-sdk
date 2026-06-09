# CLAUDE.md — DPP SDK (Python)

## What this project is

This is the **Python port** of the Java **Digital Product Passport (DPP) SDK**. The goal is to
reproduce the same functionality as an *idiomatic Python SDK* using **Pydantic v2**.

The project is currently **empty except for this file and `docs/PORTING_PLAN.md`** — the port has
not been started yet. Read `docs/PORTING_PLAN.md` first; it is the agreed plan and the source of
truth for scope, design decisions, and the execution outline.

## ⭐ The reference implementation lives next door

The Java SDK being ported is in the **sibling directory `../dpp-sdk-platform`**. **Open and read it
whenever you need to understand intended behavior** — it is the authoritative spec. Key locations:

- `../dpp-sdk-platform/dpp-datamodel/dpp-core/src/main/java/dppsdk/core/` — core models, mappers,
  validators, payloads, util.
- `../dpp-sdk-platform/dpp-datamodel/dpp4fun/src/main/java/dppsdk/dpp4fun/` — furniture-specific
  models, mappers, validators, and `transport/Dpp4FunJsonCodec.java` (the JSON codec to replicate).
- `../dpp-sdk-platform/dpp-datamodel/VALIDATION_RULES.md` and `VALIDATION_GUIDE.md` — **the exact
  validation rules to re-encode** (50+ checks). Treat these as the test spec.
- `../dpp-sdk-platform/dpp-datamodel/SDK_USAGE.md`, `MODEL_GUIDE.md`, `DPP_SDK_OVERVIEW.md` —
  intended consumer usage and model principles.
- `../dpp-sdk-platform/dpp-sdk-clients/` — `dpp-repo-client` / `dpp-registry-client` (the HTTP
  clients to port) and their payload DTOs.
- `../dpp-sdk-platform/dpp-sdk-demo/` — Spring Boot mock repo + EU registry. **Do not port these.**
  Reuse them as a running conformance oracle to test the Python clients against.
- Test data factories worth mirroring as pytest fixtures:
  `.../dpp4fun/src/test/java/dppsdk/support/TestDataFactory.java` and
  `.../dpp-core/src/test/java/dppsdk/core/support/CoreTestDataFactory.java`.

## Scope (decided with the user)

- **In scope:** datamodel (`dpp-core` + `dpp4fun`) **and** HTTP clients (repo + registry).
- **Out of scope:** the Spring Boot mock services / integration demo (oracle only).
- **Fidelity:** idiomatic Pydantic v2 — collapse the Java model/builder/validator/mapper/codec
  layers into declarative models. Do **not** mirror the Java class-per-layer structure.

## Tech stack & conventions

- **Python 3.11+**, **Pydantic v2** (models, validation, JSON), **httpx** (HTTP clients),
  **pytest**, **mypy**, **ruff**. (No `jsonpatch`: the clients forward caller-supplied JSON
  partials as the PATCH body, exactly like the Java client — they don't build RFC 6902 patches.)
- **Packaging:** PEP 621 `pyproject.toml`, `src/` layout, `py.typed` marker.
- **Package layout:** one package `dpp_sdk` with sub-packages `dpp_sdk.core`, `dpp_sdk.dpp4fun`,
  `dpp_sdk.clients`.
- Immutable models via `ConfigDict(frozen=True)`; use `tuple` for collection fields where the Java
  side returns defensive copies. Java `toBuilder()` edits → `model_copy(update=...)`.
- Mirror Jackson `@JsonProperty` names with Pydantic `Field(alias=...)` + `populate_by_name=True`.

## Two things to get exactly right (highest-risk areas)

1. **Flat vs. nested JSON transport.** Outbound JSON is *flattened* (coreDpp fields lifted to
   root); inbound accepts *both* flat and nested. Implement via `@model_serializer` (out) +
   `@model_validator(mode="before")` (in). Pin byte-for-byte parity with the Java codec using
   golden files captured from the Java SDK.
2. **Validation parity.** Re-encode every rule in `VALIDATION_RULES.md`; for each, add a passing
   and a failing test. Note the intentional fail-fast (Java) → collect-all (Pydantic) difference.

## How to work

- Start from `docs/PORTING_PLAN.md`'s execution outline (skeleton → core models → core validation
  → dpp4fun → transport → clients → tests).
- When behavior is ambiguous, **read the Java source in `../dpp-sdk-platform` rather than
  guessing.**
- Keep `pytest` green, `mypy` clean, and `ruff` clean as you go.
- This is a fresh git project; initialize git and commit in logical increments (ask before pushing
  anywhere).
