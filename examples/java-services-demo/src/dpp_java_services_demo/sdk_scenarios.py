"""Assertion-based SDK-01 through SDK-15 capability demonstrations."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from time import perf_counter
from typing import NamedTuple
from uuid import UUID

import httpx
from dpp_sdk import (
    BillOfMaterials,
    Characteristics,
    Dimensions,
    Dpp4Fun,
    Dpp4FunJsonCodec,
    DppError,
    DppMappingError,
    DppValidationError,
    Material,
    OrganizationRole,
    from_json,
    from_json_and_validate,
    to_json,
    validate_dpp4fun,
    validate_dpp_core,
)
from dpp_sdk.clients import (
    DppApiClientError,
    DppClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppRegistryClient,
    DppRepoClient,
    DppValidationClientError,
)
from pydantic import ValidationError

from .fixtures import (
    DemoIdentity,
    build_complete_fixture,
    build_minimal_fixture,
    new_demo_identity,
)
from .reporting import ScenarioResult, ScenarioStatus


class _ScenarioContext(NamedTuple):
    identity: DemoIdentity
    complete: Dpp4Fun
    minimal: Dpp4Fun


class _Outcome(NamedTuple):
    summary: str
    details: str = ""


class _Scenario(NamedTuple):
    scenario_id: str
    name: str
    category: str
    run: Callable[[_ScenarioContext], _Outcome]


def _expect(
    exception_type: type[BaseException],
    operation: Callable[[], object],
    contains: str | None = None,
) -> BaseException:
    try:
        operation()
    except exception_type as exc:
        if contains is not None and contains not in str(exc):
            raise AssertionError(
                f"Expected {exception_type.__name__} containing {contains!r}, got {exc!s}"
            ) from exc
        return exc
    raise AssertionError(f"Expected {exception_type.__name__}")


def _sdk_01(context: _ScenarioContext) -> _Outcome:
    fixture = context.complete
    assert fixture.documentation is not None
    assert fixture.billOfMaterials is not None
    assert fixture.manufacturer is not None and fixture.manufacturer.contact is not None
    assert isinstance(fixture.tags, tuple)
    assert isinstance(fixture.features, tuple)
    assert isinstance(fixture.billOfMaterials.materials, tuple)
    return _Outcome("Complete typed model constructed", "All optional model groups are populated")


def _sdk_02(context: _ScenarioContext) -> _Outcome:
    fixture = context.minimal
    validate_dpp4fun(fixture)
    assert fixture.documentation is None
    assert fixture.billOfMaterials is None
    return _Outcome("Minimal valid model constructed", "Documentation and BOM are omitted")


def _sdk_03(context: _ScenarioContext) -> _Outcome:
    fixture = context.complete
    assert fixture.dpp_id == str(context.identity.dpp_id)
    assert fixture.product_id == context.identity.product_id
    assert fixture.uniqueProductIdentifier == context.identity.dpp_id
    assert fixture.gtinCode == context.identity.product_id
    return _Outcome("DPP and product identifiers extracted from public properties")


def _sdk_04(context: _ScenarioContext) -> _Outcome:
    complete = context.complete
    validate_dpp_core(complete.coreDpp)
    future_metadata = complete.passportMetadata.with_updates(
        passportUpdateDates=(date.today() + timedelta(days=1),)
    )
    future_core = complete.coreDpp.with_updates(passportMetadata=future_metadata)
    no_organization = complete.nameplate.with_updates(manufacturer=None, supplier=None)
    wrong_role = complete.manufacturer
    assert wrong_role is not None
    wrong_role = wrong_role.with_updates(role=OrganizationRole.SUPPLIER)
    bad_role_nameplate = complete.nameplate.with_updates(manufacturer=wrong_role)
    contact = complete.manufacturer.contact
    assert contact is not None
    bad_email = contact.email
    assert bad_email is not None
    bad_email = bad_email.with_updates(emailAddress="invalid-email")
    bad_contact = contact.with_updates(email=bad_email)
    bad_contact_manufacturer = complete.manufacturer.with_updates(contact=bad_contact)
    bad_contact_nameplate = complete.nameplate.with_updates(manufacturer=bad_contact_manufacturer)
    invalid_docs = complete.coreDpp.documentation
    assert invalid_docs is not None
    invalid_docs = invalid_docs.with_updates(
        digitalInstructionsLink=None,
        safetyInstructionsLink=None,
        downloadable=True,
    )
    invalid_cores = (
        future_core,
        complete.coreDpp.with_updates(nameplate=no_organization),
        complete.coreDpp.with_updates(nameplate=bad_role_nameplate),
        complete.coreDpp.with_updates(nameplate=bad_contact_nameplate),
        complete.coreDpp.with_updates(documentation=invalid_docs),
    )
    for core in invalid_cores:
        _expect(DppValidationError, lambda core=core: validate_dpp_core(core))
    return _Outcome(
        "Core validation accepted valid data and rejected five semantic violations",
        "future date; missing organization; wrong role; invalid email; invalid documentation",
    )


def _sdk_05(context: _ScenarioContext) -> _Outcome:
    complete = context.complete
    validate_dpp4fun(complete)
    validate_dpp4fun(context.minimal)
    future_metadata = complete.passportMetadata.with_updates(
        passportUpdateDates=(date.today() + timedelta(days=1),)
    )
    invalid_core = complete.coreDpp.with_updates(passportMetadata=future_metadata)
    invalid_classification = complete.classification.with_updates(tags=("Chair", " chair "))
    invalid_characteristics = complete.characteristics.with_updates(
        features=("adjustable", "ADJUSTABLE")
    )
    invalid_bom = BillOfMaterials(
        materials=(
            Material(name="Steel", portion=0.5, reference="R1"),
            Material(name=" steel ", portion=0.5, reference="r1"),
        )
    )
    invalid_cross = complete.characteristics.with_updates(productType="Table")
    invalid_aggregates = (
        complete.with_updates(coreDpp=invalid_core),
        complete.with_updates(classification=invalid_classification),
        complete.with_updates(characteristics=invalid_characteristics),
        complete.with_updates(billOfMaterials=invalid_bom),
        complete.with_updates(characteristics=invalid_cross),
    )
    for aggregate in invalid_aggregates:
        _expect(DppValidationError, lambda aggregate=aggregate: validate_dpp4fun(aggregate))
    combined = complete.with_updates(
        coreDpp=invalid_core,
        classification=invalid_classification,
        characteristics=invalid_characteristics,
    )
    _expect(DppValidationError, lambda: validate_dpp4fun(combined), "passportUpdateDates[0]")
    return _Outcome(
        "Aggregate validation and fail-fast order demonstrated",
        "core; classification; characteristics; BOM; cross-object rule",
    )


def _sdk_06(context: _ScenarioContext) -> _Outcome:
    complete = context.complete
    raw = to_json(complete)
    flat = json.loads(raw)
    assert "coreDpp" not in flat
    assert {"passportMetadata", "nameplate", "documentation"} <= flat.keys()
    assert from_json(raw) == complete
    nested_raw = complete.model_dump_json()
    assert from_json(nested_raw) == complete
    duplicate = dict(flat)
    duplicate["nameplate"] = {**duplicate["nameplate"], "gtinCode": "flat-loses"}
    duplicate["coreDpp"] = complete.coreDpp.model_dump(mode="json")
    assert from_json(json.dumps(duplicate)).product_id == complete.product_id
    assert from_json_and_validate(raw) == complete
    future = complete.with_updates(
        coreDpp=complete.coreDpp.with_updates(
            passportMetadata=complete.passportMetadata.with_updates(
                passportUpdateDates=(date.today() + timedelta(days=1),)
            )
        )
    )
    future_raw = to_json(future)
    assert from_json(future_raw) == future
    _expect(DppValidationError, lambda: from_json_and_validate(future_raw))
    codec = Dpp4FunJsonCodec()
    assert codec.from_json(codec.to_json(complete)) == complete
    return _Outcome(
        "Flat/nested codec and semantic round trip demonstrated",
        "nested core wins duplicates; validated parsing remains explicit",
    )


def _sdk_07(context: _ScenarioContext) -> _Outcome:
    original = context.complete
    changed_characteristics = original.characteristics.with_updates(
        productName="Updated Demo Chair"
    )
    changed_metadata = original.passportMetadata.with_updates(qrCodeOrDigitalTag="UPDATED-QR")
    changed_core = original.coreDpp.with_updates(passportMetadata=changed_metadata)
    updated = original.with_updates(
        characteristics=changed_characteristics,
        coreDpp=changed_core,
    )
    validate_dpp4fun(updated)
    assert updated is not original
    assert type(updated) is type(original)
    assert updated.productName == "Updated Demo Chair"
    assert original.productName == "CIR4FUN Demo Chair"
    assert original.qrCodeOrDigitalTag == context.identity.registry_sensitive_id
    return _Outcome(
        "Valid immutable nested updates preserved subtype",
        "Original instance remained unchanged",
    )


def _sdk_08(context: _ScenarioContext) -> _Outcome:
    complete = context.complete
    _expect(ValidationError, lambda: complete.characteristics.with_updates(productName=" "))
    _expect(ValidationError, lambda: complete.characteristics.with_updates(weight=float("inf")))
    semantic_bad = complete.with_updates(
        characteristics=complete.characteristics.with_updates(productType="Table")
    )
    _expect(DppValidationError, lambda: validate_dpp4fun(semantic_bad), "inconsistent")
    return _Outcome(
        "Invalid immutable updates rejected at the correct boundary",
        "blank and infinity are structural; cross-object mismatch is semantic",
    )


def _sdk_09(context: _ScenarioContext) -> _Outcome:
    _expect(ValidationError, lambda: Characteristics(productName=" "))
    _expect(
        DppValidationError,
        lambda: validate_dpp4fun(
            context.complete.with_updates(
                characteristics=context.complete.characteristics.with_updates(productType="Table")
            )
        ),
    )
    _expect(DppMappingError, lambda: from_json("null"))
    assert issubclass(DppValidationError, DppError)
    assert issubclass(DppMappingError, DppError)
    client_categories = (
        DppValidationClientError,
        DppMappingClientError,
        DppNetworkClientError,
        DppHttpClientError,
        DppApiClientError,
    )
    assert all(issubclass(category, DppClientError) for category in client_categories)
    return _Outcome(
        "Public structural, SDK, mapping, and client error categories demonstrated",
        "Five public client error categories share DppClientError",
    )


def _sdk_10(_context: _ScenarioContext) -> _Outcome:
    rejected = (" ", "\t", "\n", "\u00a0", "\u202f", "\u2003")
    for value in rejected:
        _expect(ValidationError, lambda value=value: Characteristics(productName=value))
    assert Characteristics(productName="\u200b").productName == "\u200b"
    mixed = "\u00a0 Demo Chair \u2003"
    assert Characteristics(productName=mixed).productName == mixed
    return _Outcome(
        "Approved Unicode whitespace table demonstrated",
        "ASCII/tab/newline/NBSP/narrow-NBSP/em-space reject; U+200B and mixed text retain",
    )


def _sdk_11(context: _ScenarioContext) -> _Outcome:
    assert Characteristics(productName="Chair", weight=0.0).weight == 0.0
    assert Dimensions(width=1.25e2, height=1.0, depth=1.0, unit="cm").width == 125.0
    assert Material(name="Steel", portion=1.25e-2).portion == 0.0125
    for value in (-1.0, float("nan"), float("inf"), float("-inf")):
        _expect(
            ValidationError,
            lambda value=value: Characteristics(productName="Chair", weight=value),
        )
    raw = to_json(context.complete)
    assert all(token not in raw for token in ("NaN", "Infinity", "-Infinity"))
    overflow = json.loads(raw)
    overflow["characteristics"]["weight"] = 1e400
    _expect(DppMappingError, lambda: from_json(json.dumps(overflow)))
    return _Outcome(
        "Finite non-negative numeric contract demonstrated",
        "zero/positive/exponent accept; negative/NaN/infinities/overflow reject",
    )


def _sdk_12(context: _ScenarioContext) -> _Outcome:
    for raw in ("null", "", "{}"):
        _expect(DppMappingError, lambda raw=raw: from_json(raw))
    payload = json.loads(to_json(context.complete))
    payload["classification"]["tags"] = [None]
    _expect(DppMappingError, lambda: from_json(json.dumps(payload)))
    payload["classification"]["tags"] = [" "]
    assert from_json(json.dumps(payload)).tags == (" ",)
    _expect(DppValidationError, lambda: from_json_and_validate(json.dumps(payload)))
    registry = DppRegistryClient("http://localhost:8081")
    try:
        client_error = _expect(
            DppMappingClientError,
            lambda: registry.post_new_dpp_to_registry(None),  # type: ignore[arg-type]
        )
        assert isinstance(client_error.__cause__, ValueError)
    finally:
        registry.close()
    return _Outcome(
        "Root, list-member, and required client null contracts demonstrated",
        "root null/empty/object and null members map-fail; blank member validates-fail",
    )


def _sdk_13(context: _ScenarioContext) -> _Outcome:
    _expect(DppValidationError, lambda: validate_dpp4fun(None), "cannot be null")
    complete = context.complete
    future_metadata = complete.passportMetadata.with_updates(
        passportUpdateDates=(date.today() + timedelta(days=1),)
    )
    invalid = complete.with_updates(
        coreDpp=complete.coreDpp.with_updates(passportMetadata=future_metadata),
        classification=complete.classification.with_updates(tags=("Chair", "chair")),
    )
    _expect(DppValidationError, lambda: validate_dpp4fun(invalid), "passportUpdateDates[0]")
    return _Outcome(
        "Aggregate null guard and supported fail-fast order demonstrated",
        "Core validation precedes later aggregate groups",
    )


def _sdk_14(context: _ScenarioContext) -> _Outcome:
    empty_bom = context.minimal.with_updates(billOfMaterials=BillOfMaterials())
    bom_json = json.loads(to_json(empty_bom))["billOfMaterials"]
    assert bom_json == {"materials": [], "components": [], "parts": []}
    duplicate_bom = BillOfMaterials(
        materials=(
            Material(name="Steel", portion=0.5, reference=" R1 "),
            Material(name="\u202fsteel\u2003", portion=0.5, reference="r1"),
        )
    )
    invalid = context.complete.with_updates(billOfMaterials=duplicate_bom)
    _expect(DppValidationError, lambda: validate_dpp4fun(invalid), "duplicate")
    null_member = json.loads(to_json(context.complete))
    null_member["billOfMaterials"]["materials"] = [None]
    _expect(DppMappingError, lambda: from_json(json.dumps(null_member)))
    return _Outcome(
        "Bill of Materials arrays and errors demonstrated",
        "empty arrays serialize; normalized duplicate and null member reject",
    )


def _sdk_15(_context: _ScenarioContext) -> _Outcome:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    injected = httpx.Client(transport=transport)
    codec = Dpp4FunJsonCodec()
    with DppRepoClient(
        "http://localhost:8080",
        codec,
        validate_dpp4fun,
        client=injected,
    ):
        pass
    with DppRegistryClient("http://localhost:8081", client=injected):
        pass
    assert not injected.is_closed
    injected.close()
    owned_repo = DppRepoClient("http://localhost:8080", codec, validate_dpp4fun)
    owned_registry = DppRegistryClient("http://localhost:8081")
    owned_repo.close()
    owned_repo.close()
    owned_registry.close()
    owned_registry.close()
    return _Outcome(
        "Client resource ownership demonstrated",
        "owned clients close idempotently; injected HTTPX client remains caller-owned",
    )


SCENARIOS: list[_Scenario] = [
    _Scenario("SDK-01", "Complete model construction", "SDK_LOCAL", _sdk_01),
    _Scenario("SDK-02", "Minimal model construction", "SDK_LOCAL", _sdk_02),
    _Scenario("SDK-03", "Identifier extraction", "SDK_LOCAL", _sdk_03),
    _Scenario("SDK-04", "Core semantic validation", "SDK_LOCAL", _sdk_04),
    _Scenario("SDK-05", "Aggregate semantic validation", "SDK_LOCAL", _sdk_05),
    _Scenario("SDK-06", "Codec and semantic round trip", "SDK_LOCAL", _sdk_06),
    _Scenario("SDK-07", "Valid immutable updates", "SDK_LOCAL", _sdk_07),
    _Scenario("SDK-08", "Rejected immutable updates", "SDK_LOCAL", _sdk_08),
    _Scenario("SDK-09", "Public error hierarchy", "SDK_LOCAL", _sdk_09),
    _Scenario("SDK-10", "Whitespace contract", "SDK_LOCAL", _sdk_10),
    _Scenario("SDK-11", "Finite numeric contract", "SDK_LOCAL", _sdk_11),
    _Scenario("SDK-12", "Null and root contract", "SDK_LOCAL", _sdk_12),
    _Scenario("SDK-13", "Aggregate guard and fail-fast order", "SDK_LOCAL", _sdk_13),
    _Scenario("SDK-14", "Bill of Materials contract", "SDK_LOCAL", _sdk_14),
    _Scenario("SDK-15", "Client resource ownership", "CONTROLLED", _sdk_15),
]


def run_sdk_scenarios(run_id: UUID | None = None) -> tuple[ScenarioResult, ...]:
    """Execute all approved SDK-local scenarios without requiring Docker."""

    identity = DemoIdentity.from_run_id(run_id) if run_id is not None else new_demo_identity()
    context = _ScenarioContext(
        identity,
        build_complete_fixture(identity),
        build_minimal_fixture(identity),
    )
    results: list[ScenarioResult] = []
    for scenario in SCENARIOS:
        started = perf_counter()
        try:
            outcome = scenario.run(context)
        except Exception as exc:  # noqa: BLE001 - scenario boundary reports unexpected failures
            results.append(
                ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    name=scenario.name,
                    category=scenario.category,
                    status=ScenarioStatus.FAILED,
                    duration_seconds=perf_counter() - started,
                    summary="Scenario raised an unexpected exception",
                    details=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            results.append(
                ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    name=scenario.name,
                    category=scenario.category,
                    status=ScenarioStatus.PASSED,
                    duration_seconds=perf_counter() - started,
                    summary=outcome.summary,
                    details=outcome.details,
                )
            )
    return tuple(results)
