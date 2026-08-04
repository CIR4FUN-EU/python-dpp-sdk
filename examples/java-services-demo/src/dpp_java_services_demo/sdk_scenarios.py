"""Assertion-based SDK-01 through SDK-17 capability demonstrations."""

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
    RegisterDppRequest,
)
from pydantic import ValidationError

from .fixtures import (
    DemoIdentity,
    build_complete_fixture,
    build_minimal_fixture,
    new_demo_identity,
)
from .reporting import ScenarioResult, ScenarioStatus, ScenarioTeaching


class _ScenarioContext(NamedTuple):
    identity: DemoIdentity
    complete: Dpp4Fun
    minimal: Dpp4Fun


class _Outcome(NamedTuple):
    summary: str
    details: str = ""
    input: dict[str, object] | None = None
    observed_result: dict[str, object] | None = None


class _Scenario(NamedTuple):
    scenario_id: str
    name: str
    category: str
    run: Callable[[_ScenarioContext], _Outcome]
    expected_error: bool = False
    group: str = "OTHER"
    purpose: str = ""
    operation: dict[str, str] | None = None
    expected_behavior: str = ""
    explanation: str = ""
    why_it_matters: str = ""


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
    return _Outcome(
        "Complete typed model constructed",
        "All optional model groups are populated",
        {
            "product_name": fixture.productName,
            "manufacturer": fixture.manufacturer.name,
            "documentation_links": 2,
            "bill_of_material_entries": len(fixture.billOfMaterials.materials),
        },
        {
            "model_type": type(fixture).__name__,
            "documentation_present": True,
            "bill_of_materials_present": True,
        },
    )


def _sdk_02(context: _ScenarioContext) -> _Outcome:
    fixture = context.minimal
    validate_dpp4fun(fixture)
    assert fixture.documentation is None
    assert fixture.billOfMaterials is None
    return _Outcome(
        "Minimal valid model constructed",
        "Documentation and BOM are omitted",
        {
            "product_name": fixture.productName,
            "optional_groups": ["documentation", "billOfMaterials"],
        },
        {
            "semantic_validation": "accepted",
            "documentation_present": False,
            "bill_of_materials_present": False,
        },
    )


def _sdk_03(context: _ScenarioContext) -> _Outcome:
    fixture = context.complete
    assert fixture.dpp_id == str(context.identity.dpp_id)
    assert fixture.product_id == context.identity.product_id
    assert fixture.uniqueProductIdentifier == context.identity.dpp_id
    assert fixture.gtinCode == context.identity.product_id
    return _Outcome(
        "DPP and product identifiers extracted from public properties",
        input={
            "dpp_id_field": str(context.identity.dpp_id),
            "product_id_field": context.identity.product_id,
        },
        observed_result={
            "dpp_id": fixture.dpp_id,
            "product_id": fixture.product_id,
            "public_aliases_match": True,
        },
    )


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
        {
            "valid_core": "current complete fixture",
            "invalid_cases": [
                "future passport update date",
                "missing manufacturer and supplier",
                "manufacturer with supplier role",
                "invalid contact email",
                "downloadable documentation without a link",
            ],
        },
        {
            "valid_core": "accepted",
            "rejected": [
                {
                    "input": "future passport update date",
                    "exception": "DppValidationError",
                    "path": "passportUpdateDates[0]",
                },
                {"input": "missing manufacturer and supplier", "exception": "DppValidationError"},
                {"input": "manufacturer role is SUPPLIER", "exception": "DppValidationError"},
                {"input": "invalid contact email", "exception": "DppValidationError"},
                {"input": "downloadable document without link", "exception": "DppValidationError"},
            ],
        },
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
        {
            "invalid_groups": [
                "future core date",
                "duplicate tags",
                "duplicate features",
                "duplicate BOM material",
                "product type mismatch",
            ]
        },
        {
            "valid_complete": "accepted",
            "all_invalid_groups": "rejected",
            "first_combined_error_path": "passportUpdateDates[0]",
        },
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
        {
            "source": {"product_name": complete.productName, "product_id": complete.product_id},
            "json_fragment": {
                "productName": flat["characteristics"]["productName"],
                "gtinCode": flat["nameplate"]["gtinCode"],
            },
        },
        {
            "flat_round_trip_equal": from_json(raw) == complete,
            "nested_round_trip_equal": from_json(nested_raw) == complete,
            "nested_core_precedence": complete.product_id,
            "validated_future_date": "DppValidationError",
        },
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
        {
            "before": {
                "product_name": original.productName,
                "qr_code": original.qrCodeOrDigitalTag,
            },
            "requested_update": {"product_name": "Updated Demo Chair", "qr_code": "UPDATED-QR"},
        },
        {
            "original_product_name": original.productName,
            "updated_product_name": updated.productName,
            "original_unchanged": original.qrCodeOrDigitalTag
            == context.identity.registry_sensitive_id,
            "subtype_preserved": type(updated) is type(original),
            "semantic_validation": "accepted",
        },
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
        {"invalid_updates": ["productName=' '", "weight=infinity", "productType='Table'"]},
        {
            "blank_product_name": "ValidationError",
            "infinite_weight": "ValidationError",
            "cross_object_mismatch": "DppValidationError",
            "original_unchanged": complete.productType == "Office Chair",
        },
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
        {
            "representative_operations": [
                "Characteristics(productName=' ')",
                "validate_dpp4fun(productType mismatch)",
                "from_json('null')",
            ]
        },
        {
            "structural_error": "ValidationError",
            "semantic_error": "DppValidationError",
            "mapping_error": "DppMappingError",
            "client_error_base": "DppClientError",
            "client_categories": 5,
        },
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
        {
            "values": [
                {"label": "space", "code_point": "U+0020"},
                {"label": "tab", "code_point": "U+0009"},
                {"label": "newline", "code_point": "U+000A"},
                {"label": "NBSP", "code_point": "U+00A0"},
                {"label": "narrow NBSP", "code_point": "U+202F"},
                {"label": "em space", "code_point": "U+2003"},
                {"label": "zero-width space", "code_point": "U+200B"},
            ]
        },
        {
            "whitespace_only": "six values rejected with ValidationError",
            "zero_width_space": "accepted as content",
            "mixed_visible_text": "accepted unchanged",
        },
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
        {
            "accepted": [0.0, 125.0, 0.0125],
            "rejected": ["-1.0", "NaN", "+Infinity", "-Infinity", "JSON overflow"],
        },
        {
            "zero": "accepted",
            "positive": "accepted",
            "exponent": "accepted",
            "negative": "ValidationError",
            "nan": "ValidationError",
            "positive_infinity": "ValidationError",
            "negative_infinity": "ValidationError",
            "overflow": "DppMappingError",
            "serialized_json_contains_non_finite_tokens": False,
        },
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
        {
            "codec_roots": ["null", "empty string", "{}"],
            "list_members": ["null", "blank string"],
            "client_response": "null",
        },
        {
            "invalid_roots": "DppMappingError",
            "null_list_member": "DppMappingError",
            "blank_list_member_mapping": "accepted",
            "blank_list_member_validation": "DppValidationError",
            "registry_null_response": "DppMappingClientError",
            "registry_cause": "ValueError",
        },
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
        {
            "null_aggregate": None,
            "combined_invalid_groups": ["future passport update date", "duplicate tags"],
        },
        {
            "null_aggregate": "DppValidationError",
            "first_combined_error_path": "passportUpdateDates[0]",
            "validation_order": "core before classification",
        },
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
        {
            "empty_bom": {"materials": [], "components": [], "parts": []},
            "duplicate_materials": ["Steel/R1", "steel/r1"],
            "null_material": None,
        },
        {
            "empty_bom_json": bom_json,
            "normalized_duplicate": "DppValidationError",
            "null_member": "DppMappingError",
        },
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
        {
            "injected_client": "httpx.Client(MockTransport)",
            "owned_clients": ["DppRepoClient", "DppRegistryClient"],
        },
        {
            "injected_after_sdk_context": "open",
            "owned_repo_first_close": "closed",
            "owned_repo_second_close": "no error",
            "owned_registry_first_close": "closed",
            "owned_registry_second_close": "no error",
            "caller_closed_injected": True,
        },
    )


def _sdk_16(context: _ScenarioContext) -> _Outcome:
    malformed = json.loads(to_json(context.complete))
    malformed["classification"] = {}
    error = _expect(DppMappingError, lambda: from_json(json.dumps(malformed)))
    assert error.__cause__ is not None
    return _Outcome(
        "Invalid codec input preserves its mapping cause",
        type(error.__cause__).__name__,
        {"malformed_payload": {"classification": {}}},
        {
            "public_exception": type(error).__name__,
            "underlying_cause": type(error.__cause__).__name__,
            "cause_preserved": True,
        },
    )


def _sdk_17(_context: _ScenarioContext) -> _Outcome:
    request = RegisterDppRequest(
        productIdentifier="GTIN-0001",
        dppIdentifier="DPP-1",
        operatorIdentifier="operator-1",
        repoUrl="https://repo.example.com",
    )
    assert request.model_dump()["dppApiEndpoint"] == "https://repo.example.com"
    return _Outcome(
        "Registry request aliases emit canonical public JSON",
        "canonical dppApiEndpoint",
        {"constructor_alias": {"repoUrl": "https://repo.example.com"}},
        {
            "canonical_output_key": "dppApiEndpoint",
            "canonical_output_value": request.model_dump()["dppApiEndpoint"],
        },
    )


SCENARIOS: list[_Scenario] = [
    _Scenario(
        "SDK-01",
        "Complete model construction",
        "SDK_LOCAL",
        _sdk_01,
        group="MODELS_AND_IDENTIFIERS",
        purpose="Construct a complete typed DPP with supported optional groups.",
        operation={"public_api": "Dpp4Fun", "display": "dpp = Dpp4Fun(...)"},
        expected_behavior=(
            "The nested model is structurally valid and retains typed optional groups."
        ),
        explanation="Pydantic constructs the nested model and its immutable collections.",
        why_it_matters="Consumers work with typed fields instead of manually assembling raw JSON.",
    ),
    _Scenario(
        "SDK-02",
        "Minimal model construction",
        "SDK_LOCAL",
        _sdk_02,
        group="MODELS_AND_IDENTIFIERS",
        purpose="Show that optional documentation and BOM groups may be omitted.",
        operation={"public_api": "validate_dpp4fun", "display": "validate_dpp4fun(minimal_dpp)"},
        expected_behavior="A minimal supported DPP passes semantic validation.",
        explanation="Optional model groups are not required for a valid minimal passport.",
        why_it_matters="Consumers can start with the fields their use case actually has.",
    ),
    _Scenario(
        "SDK-03",
        "Identifier extraction",
        "SDK_LOCAL",
        _sdk_03,
        group="MODELS_AND_IDENTIFIERS",
        purpose="Read DPP and product identifiers through public model properties.",
        operation={
            "public_api": "Dpp4Fun.dpp_id / product_id",
            "display": "dpp.dpp_id; dpp.product_id",
        },
        expected_behavior="Public aliases return the canonical identifier values.",
        explanation=(
            "The SDK exposes stable properties rather than requiring callers to traverse nested "
            "fields."
        ),
        why_it_matters=(
            "Application code can retrieve identifiers without coupling to internal model layout."
        ),
    ),
    _Scenario(
        "SDK-04",
        "Core semantic validation",
        "SDK_LOCAL",
        _sdk_04,
        True,
        "VALIDATION",
        "Demonstrate semantic validation after structurally valid construction.",
        {"public_api": "validate_dpp_core", "display": "validate_dpp_core(dpp.coreDpp)"},
        "Valid core data passes; each semantic violation raises DppValidationError.",
        "Semantic rules cover dates, organization roles, contact data, and documentation "
        "consistency.",
        "Consumers receive a public validation category before relying on business data.",
    ),
    _Scenario(
        "SDK-05",
        "Aggregate semantic validation",
        "SDK_LOCAL",
        _sdk_05,
        True,
        "VALIDATION",
        "Demonstrate cross-object validation and deterministic fail-fast order.",
        {"public_api": "validate_dpp4fun", "display": "validate_dpp4fun(dpp)"},
        "Aggregate duplicates and mismatches reject with the first supported path.",
        "Aggregate validation checks relationships that a single nested model cannot see.",
        "A stable first error lets consumers surface consistent remediation.",
    ),
    _Scenario(
        "SDK-06",
        "Codec and semantic round trip",
        "SDK_LOCAL",
        _sdk_06,
        False,
        "CODECS_AND_MAPPING",
        "Serialize a DPP, decode it, and opt into semantic validation.",
        {
            "public_api": "to_json / from_json / from_json_and_validate",
            "display": "decoded = from_json_and_validate(to_json(dpp))",
        },
        "Flat and nested payloads round-trip; semantic-invalid JSON rejects only when "
        "validated parsing is requested.",
        "Mapping and semantic validation are deliberately separate SDK stages.",
        "Consumers can choose fast mapping or validated input according to their trust boundary.",
    ),
    _Scenario(
        "SDK-07",
        "Valid immutable updates",
        "SDK_LOCAL",
        _sdk_07,
        False,
        "IMMUTABLE_UPDATES",
        "Change nested values by creating a validated replacement DPP.",
        {"public_api": "Dpp4Fun.with_updates", "display": "updated = dpp.with_updates(...)"},
        "The replacement is validated, keeps its subtype, and leaves the original unchanged.",
        "The SDK creates a new immutable instance instead of mutating the existing passport.",
        "Immutable updates avoid partially changed shared objects.",
    ),
    _Scenario(
        "SDK-08",
        "Rejected immutable updates",
        "SDK_LOCAL",
        _sdk_08,
        True,
        "IMMUTABLE_UPDATES",
        "Show structural and semantic checks applied to requested updates.",
        {
            "public_api": "with_updates / validate_dpp4fun",
            "display": "dpp.with_updates(...); validate_dpp4fun(updated)",
        },
        "Blank/infinite values reject structurally; cross-object mismatch rejects semantically.",
        "Update construction and aggregate validation protect different contract boundaries.",
        "Consumers can distinguish bad field data from invalid relationships.",
    ),
    _Scenario(
        "SDK-09",
        "Public error hierarchy",
        "SDK_LOCAL",
        _sdk_09,
        False,
        "ERRORS_AND_CLIENT_OWNERSHIP",
        "Identify the public error families consumers can catch.",
        {
            "public_api": "DppError and DppClientError",
            "display": "except DppError: ...; except DppClientError: ...",
        },
        "Structural, semantic, mapping, and client categories stay distinct.",
        "The SDK preserves error categories instead of flattening all failures.",
        "Consumers may catch broadly or react to a precise public failure type.",
    ),
    _Scenario(
        "SDK-10",
        "Whitespace contract",
        "SDK_LOCAL",
        _sdk_10,
        True,
        "BOUNDARY_CONTRACTS",
        "Show which Unicode whitespace-only values are rejected as blank.",
        {"public_api": "Characteristics", "display": "Characteristics(productName=value)"},
        "Whitespace-only values reject; zero-width and mixed visible text remain content.",
        "Blank checks use the documented Unicode whitespace behavior.",
        "Consumers can validate internationalized input predictably.",
    ),
    _Scenario(
        "SDK-11",
        "Finite numeric contract",
        "SDK_LOCAL",
        _sdk_11,
        True,
        "BOUNDARY_CONTRACTS",
        "Show finite, non-negative numeric requirements and JSON safety.",
        {
            "public_api": "Characteristics / Dimensions / from_json",
            "display": "Characteristics(productName='Chair', weight=value)",
        },
        "Zero and finite positive values pass; negative/non-finite/overflow values reject.",
        "The SDK refuses values that cannot be represented safely in JSON.",
        "Consumers avoid emitting invalid numeric payloads.",
    ),
    _Scenario(
        "SDK-12",
        "Null and root contract",
        "SDK_LOCAL",
        _sdk_12,
        True,
        "CODECS_AND_MAPPING",
        "Distinguish invalid codec roots, null members, blank members, and a null client response.",
        {
            "public_api": (
                "from_json / from_json_and_validate / DppRegistryClient.post_new_dpp_to_registry"
            ),
            "display": "from_json(payload); registry.post_new_dpp_to_registry(None)",
        },
        "Invalid roots/null members map-fail; blank member fails semantic validation; client "
        "null maps with a cause.",
        "The SDK reports whether failure occurred during mapping, semantic validation, or "
        "client translation.",
        "Consumers get actionable error handling at each input boundary.",
    ),
    _Scenario(
        "SDK-13",
        "Aggregate guard and fail-fast order",
        "SDK_LOCAL",
        _sdk_13,
        True,
        "VALIDATION",
        "Show aggregate null protection and first-error ordering.",
        {"public_api": "validate_dpp4fun", "display": "validate_dpp4fun(value)"},
        "None rejects and core validation reports before later aggregate defects.",
        "The aggregate validator has an explicit stable validation sequence.",
        "Consumers can reliably highlight the first corrective action.",
    ),
    _Scenario(
        "SDK-14",
        "Bill of Materials contract",
        "SDK_LOCAL",
        _sdk_14,
        True,
        "BOUNDARY_CONTRACTS",
        "Show clean empty BOM serialization and protected collection boundaries.",
        {
            "public_api": "BillOfMaterials / to_json / validate_dpp4fun",
            "display": "to_json(dpp.with_updates(billOfMaterials=BillOfMaterials()))",
        },
        "Empty categories serialize as arrays; normalized duplicates and null members reject.",
        "The SDK normalizes collection identity and blocks invalid wire members.",
        "Consumers receive clean payloads and predictable BOM validation.",
    ),
    _Scenario(
        "SDK-15",
        "Client resource ownership",
        "CONTROLLED",
        _sdk_15,
        False,
        "ERRORS_AND_CLIENT_OWNERSHIP",
        "Show the difference between SDK-owned and caller-injected HTTPX clients.",
        {
            "public_api": "DppRepoClient.close / DppRegistryClient.close",
            "display": "client.close()",
        },
        "Owned clients close idempotently; injected clients remain caller-owned.",
        "Client construction records ownership so context-manager cleanup is safe.",
        "Consumers can share injected transports without unexpected closure.",
    ),
    _Scenario(
        "SDK-16",
        "Codec mapping cause",
        "SDK_LOCAL",
        _sdk_16,
        True,
        "CODECS_AND_MAPPING",
        "Show that malformed mapped data retains its underlying cause.",
        {"public_api": "from_json", "display": "from_json(malformed_payload)"},
        "Malformed classification raises DppMappingError with a Pydantic ValidationError cause.",
        "Mapping translation preserves diagnostic cause information.",
        "Consumers can catch the public error while still logging the underlying reason.",
    ),
    _Scenario(
        "SDK-17",
        "Registry request construction",
        "CONTROLLED",
        _sdk_17,
        False,
        "ERRORS_AND_CLIENT_OWNERSHIP",
        "Show an accepted request alias and canonical emitted JSON field.",
        {
            "public_api": "RegisterDppRequest",
            "display": "RegisterDppRequest(repoUrl='https://repo.example.com')",
        },
        "The repoUrl input alias emits canonical dppApiEndpoint output.",
        "The request model normalizes supported input aliases to the public wire contract.",
        "Consumers can migrate input names without sending an incorrect API field.",
    ),
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
            if outcome.input is None or outcome.observed_result is None:
                raise AssertionError(
                    f"{scenario.scenario_id} did not capture its structured teaching evidence"
                )
            if scenario.operation is None:
                raise AssertionError(f"{scenario.scenario_id} has no public operation metadata")
            results.append(
                ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    name=scenario.name,
                    category=scenario.category,
                    status=(
                        ScenarioStatus.EXPECTED_ERROR
                        if scenario.expected_error
                        else ScenarioStatus.PASSED
                    ),
                    duration_seconds=perf_counter() - started,
                    summary=outcome.summary,
                    details=outcome.details,
                    teaching=ScenarioTeaching(
                        group=scenario.group,
                        evidence_class=scenario.category,
                        purpose=scenario.purpose,
                        input=outcome.input,
                        operation=scenario.operation,
                        expected_behavior=scenario.expected_behavior,
                        observed_result=outcome.observed_result,
                        explanation=scenario.explanation,
                        why_it_matters=scenario.why_it_matters,
                    ),
                )
            )
    return tuple(results)
