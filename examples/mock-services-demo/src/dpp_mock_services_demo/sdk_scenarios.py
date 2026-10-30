"""Annotated, offline examples using the final Python SDK public API."""

from __future__ import annotations

import json
from collections.abc import Callable
from time import perf_counter
from typing import NamedTuple
from uuid import UUID

import httpx
from dpp_sdk import (
    Dpp4Fun,
    Dpp4FunJsonCodec,
    DppHeader,
    Granularity,
    SingleValuedDataElement,
    validate_dpp4fun,
)
from dpp_sdk.clients import (
    DppApiClientError,
    DppApiMessage,
    DppApiResponse,
    DppMappingClientError,
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    DppStatusCode,
    MessageType,
    RegisterDppRequest,
)
from dpp_sdk.dpp4fun import (
    DPP4FUN_PROFILE,
    ChairCharacteristics,
    CribCharacteristics,
    Dpp4FunQuantity,
    FabricCharacteristics,
    LengthUnit,
    LockerCharacteristics,
    Nameplate,
    ParticleBoardCharacteristics,
    SofaCharacteristics,
)

from .fixtures import DemoIdentity, build_complete_fixture
from .reporting import ScenarioResult, ScenarioStatus, ScenarioTeaching


class _Outcome(NamedTuple):
    summary: str
    input: dict[str, object]
    observed_result: dict[str, object]


class _Scenario(NamedTuple):
    scenario_id: str
    name: str
    run: Callable[[DemoIdentity, Dpp4Fun], _Outcome]
    expected_error: bool
    group: str
    purpose: str
    operation: dict[str, str]
    expected_behavior: str
    explanation: str
    why_it_matters: str


def _typed_passport(identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    result = validate_dpp4fun(passport)
    if not result.is_valid:
        raise AssertionError(f"fixture has semantic issues: {result.issues!r}")
    return _Outcome(
        "typed DPP4Fun passport validates",
        {"dppId": str(identity.dpp_id), "productId": identity.product_id},
        {"valid": result.is_valid, "aspects": len(passport.passport.data_elements)},
    )


def _immutable_edit(_identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    chair = passport.typed_aspect(ChairCharacteristics)
    if chair is None:
        raise AssertionError("demo fixture has no ChairCharacteristics")
    updated = passport.with_updates(aspects=(chair.with_field("color", "green"),))
    updated_chair = updated.typed_aspect(ChairCharacteristics)
    if updated_chair is None or chair.field("color").value != "blue":
        raise AssertionError("the original aspect was mutated")
    return _Outcome(
        "updated aspect is immutable",
        {"field": "characteristics.color", "value": "green"},
        {"original": chair.field("color").value, "updated": updated_chair.field("color").value},
    )


def _codec_roundtrip(_identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    codec = Dpp4FunJsonCodec()
    full = codec.to_expanded_json(passport)
    compressed = codec.to_compressed_json(passport)
    restored = codec.from_compressed_json(compressed)
    if json.loads(codec.to_expanded_json(restored)) != json.loads(full):
        raise AssertionError("FULL -> COMPRESSED -> FULL JSON differs")
    return _Outcome(
        "canonical FULL and COMPRESSED representations agree",
        {"representations": ["FULL", "COMPRESSED"]},
        {"full_elements": len(json.loads(full)["elements"]), "equal": True},
    )


def _profile_catalog(_identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    definitions = DPP4FUN_PROFILE.definitions
    if len(definitions) != 488:
        raise AssertionError(f"unexpected profile definition count: {len(definitions)}")
    return _Outcome(
        "source-backed semantic profile is available",
        {"profile_version": DPP4FUN_PROFILE.metadata["profileVersion"]},
        {"definitions": len(definitions)},
    )


def _characteristics_variants(_identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    variants = (
        ChairCharacteristics,
        CribCharacteristics,
        FabricCharacteristics,
        LockerCharacteristics,
        ParticleBoardCharacteristics,
        SofaCharacteristics,
    )
    selected = []
    for variant in variants:
        value = Dpp4Fun.create(passport.header, variant.create(color="blue"))
        if not validate_dpp4fun(value).is_valid:
            raise AssertionError(f"{variant.__name__} fixture is invalid")
        selected.append(value.selected_characteristics().variant.value)
    return _Outcome(
        "all six typed Characteristics variants validate",
        {"variants": [item.__name__ for item in variants]},
        {"selected": selected, "count": len(selected)},
    )


def _unit_quantity(_identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    chair = ChairCharacteristics.create().with_quantity(
        "height", Dpp4FunQuantity(value=0.82, unit=LengthUnit.METER)
    )
    quantity = chair.quantity("height")
    if quantity is None or quantity.unit is not LengthUnit.METER:
        raise AssertionError("typed height quantity did not preserve its unit")
    return _Outcome(
        "quantity retains its semantic unit",
        {"value": 0.82, "unit": "m"},
        {"value": quantity.value, "unit": quantity.unit.symbol},
    )


def _extension_preservation(identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    extension = SingleValuedDataElement(
        element_id="vendorCode",
        object_type="SingleValuedDataElement",
        value="V-1",
        value_data_type="xsd:string",
    )
    value = Dpp4Fun.create(
        DppHeader(
            digital_product_passport_id=str(identity.dpp_id),
            unique_product_identifier=identity.product_id,
            granularity=Granularity.MODEL,
            dpp_schema_version="1.0",
            dpp_status="active",
            economic_operator_id=f"operator-{identity.run_id.hex}",
        ),
        Nameplate.create(manufacturerName="Example"),
        extensions=(extension,),
    )
    codec = Dpp4FunJsonCodec()
    restored = codec.from_json(codec.to_json(value))
    if restored.passport.data_elements[-1] != extension:
        raise AssertionError("unknown extension changed during transport")
    return _Outcome(
        "unknown compatible element survives transport",
        {"elementId": "vendorCode", "dictionaryReference": None},
        {"preserved": True},
    )


def _generic_json_client(identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    wire = json.loads(Dpp4FunJsonCodec().to_json(passport))
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append({"method": request.method, "path": request.url.path})
        if json.loads(request.content) != wire:
            raise AssertionError("client changed the caller's JSON body")
        return httpx.Response(
            201,
            json={
                "statusCode": "SuccessCreated",
                "payload": {"digitalProductPassportId": str(identity.dpp_id)},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = DppRepoClient("http://repo.test", client=http).create_dpp(wire)
    if result.digital_product_passport_id != str(identity.dpp_id):
        raise AssertionError("create response did not map its canonical identifier")
    return _Outcome("repository client sends neutral JSON", wire, {"requests": requests})


def _response_message(_identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    message = DppApiMessage(message_type=MessageType.Warning, text="accepted", code="W-1")
    response = DppApiResponse(
        status_code=DppStatusCode.Success,
        payload={"accepted": True},
        message=[message],
    )
    if response.message != [message] or response.payload != {"accepted": True}:
        raise AssertionError("canonical response envelope did not retain payload/message")
    return _Outcome(
        "API response preserves canonical message and payload fields",
        {"message": [{"messageType": "Warning", "text": "accepted", "code": "W-1"}]},
        {"statusCode": response.status_code.value, "message_count": len(response.message)},
    )


def _api_error(_identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "statusCode": "ClientErrorBadRequest",
                "message": [{"messageType": "Error", "text": "invalid"}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        repo = DppRepoClient("http://repo.test", client=http)
        try:
            repo.read_dpp_by_id("invalid")
        except DppApiClientError as exc:
            if exc.http_status != 400 or exc.status_code is not DppStatusCode.ClientErrorBadRequest:
                raise AssertionError("API error status fields were not preserved") from exc
            return _Outcome(
                "structured API failure maps to DppApiClientError",
                {"http_status": 400},
                {"exception": type(exc).__name__, "status_code": exc.status_code.value},
            )
    raise AssertionError("expected DppApiClientError")


def _read_full_and_preserve_ownership(identity: DemoIdentity, passport: Dpp4Fun) -> _Outcome:
    wire = json.loads(Dpp4FunJsonCodec().to_json(passport))
    observed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        return httpx.Response(200, json={"statusCode": "Success", "payload": wire})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    repo = DppRepoClient("http://repo.test", client=http)
    response = repo.read_dpp_by_id(str(identity.dpp_id), DppRepresentation.FULL)
    repo.close()
    if http.is_closed:
        raise AssertionError("closing a wrapper closed the caller-owned HTTPX client")
    http.close()
    if "representation=full" not in observed[0] or response.payload != wire:
        raise AssertionError("FULL read did not preserve request or response")
    return _Outcome(
        "FULL read preserves JSON and caller-owned transport",
        {"representation": "full"},
        {"url": observed[0], "caller_client_open_after_wrapper_close": True},
    )


def _registry_request(identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"statusCode": "Success", "payload": {"registrationId": "registration-1"}},
        )

    request = RegisterDppRequest(
        unique_product_identifier=identity.product_id,
        digital_product_passport_id=str(identity.dpp_id),
        unique_economic_operator_identifier=identity.registry_sensitive_id,
        dpp_api_endpoint="http://repo.test/v1/dpps",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = DppRegistryClient("http://registry.test", client=http).post_new_dpp_to_registry(
            request
        )
    expected = {
        "uniqueProductIdentifier",
        "digitalProductPassportId",
        "uniqueEconomicOperatorIdentifier",
        "dppApiEndpoint",
    }
    if set(observed[0]) != expected or result.registration_id != "registration-1":
        raise AssertionError("registry wire contract differs from canonical API")
    return _Outcome(
        "registry request uses canonical JSON names",
        request.model_dump(),
        {"keys": sorted(expected)},
    )


def _invalid_registry_request(_identity: DemoIdentity, _passport: Dpp4Fun) -> _Outcome:
    with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as http:
        registry = DppRegistryClient("http://registry.test", client=http)
        try:
            registry.post_new_dpp_to_registry(None)  # type: ignore[arg-type]
        except DppMappingClientError as exc:
            return _Outcome(
                "invalid caller input is rejected before I/O",
                {"request": None},
                {"exception": type(exc).__name__, "sent": False},
            )
    raise AssertionError("expected DppMappingClientError")


def _scenario(
    scenario_id: str,
    name: str,
    run: Callable[[DemoIdentity, Dpp4Fun], _Outcome],
    public_api: str,
    display: str,
    *,
    expected_error: bool = False,
) -> _Scenario:
    return _Scenario(
        scenario_id,
        name,
        run,
        expected_error,
        "PYTHON_SDK",
        name,
        {"public_api": public_api, "display": display},
        f"{name} follows the current public SDK contract.",
        "The example uses typed models at the application boundary and JSON at HTTP.",
        "An executable example makes SDK behavior easy to verify.",
    )


SCENARIOS = [
    _scenario(
        "SDK-01",
        "Typed DPP4Fun validation",
        _typed_passport,
        "Dpp4Fun / validate_dpp4fun",
        "validate_dpp4fun(value)",
    ),
    _scenario(
        "SDK-02",
        "Immutable aspect update",
        _immutable_edit,
        "Dpp4Fun.with_updates",
        "value.with_updates(aspects=...)",
    ),
    _scenario(
        "SDK-03",
        "FULL and COMPRESSED round trip",
        _codec_roundtrip,
        "Dpp4FunJsonCodec",
        "codec.from_compressed_json(...)",
    ),
    _scenario(
        "SDK-04",
        "Semantic profile catalog",
        _profile_catalog,
        "DPP4FUN_PROFILE",
        "DPP4FUN_PROFILE.definitions",
    ),
    _scenario(
        "SDK-05",
        "Six Characteristics variants",
        _characteristics_variants,
        "Characteristics variants",
        "variant.create(color=...)",
    ),
    _scenario(
        "SDK-06",
        "Typed quantity and unit",
        _unit_quantity,
        "Dpp4FunQuantity / LengthUnit",
        "Dpp4FunQuantity(value, unit)",
    ),
    _scenario(
        "SDK-07",
        "Unknown extension preservation",
        _extension_preservation,
        "Dpp4FunJsonCodec",
        "codec.from_json(codec.to_json(value))",
    ),
    _scenario(
        "SDK-08",
        "Generic JSON repository client",
        _generic_json_client,
        "DppRepoClient.create_dpp",
        "repo.create_dpp(json_value)",
    ),
    _scenario(
        "SDK-09",
        "Response envelope and messages",
        _response_message,
        "DppApiResponse / DppApiMessage",
        "response.message",
    ),
    _scenario(
        "SDK-10", "API failure mapping", _api_error, "DppApiClientError", "repo.read_dpp_by_id(id)"
    ),
    _scenario(
        "SDK-11",
        "FULL read and client ownership",
        _read_full_and_preserve_ownership,
        "DppRepresentation.FULL",
        "repo.read_dpp_by_id(id, FULL)",
    ),
    _scenario(
        "SDK-12",
        "Invalid registry request mapping",
        _invalid_registry_request,
        "DppRegistryClient.post_new_dpp_to_registry",
        "registry.post_new_dpp_to_registry(None)",
        expected_error=True,
    ),
]


def run_sdk_scenarios(
    run_id: UUID | None = None, *, scenario_ids: tuple[str, ...] | None = None
) -> tuple[ScenarioResult, ...]:
    """Run maintained examples or an explicitly selected canonical subset."""
    identity = DemoIdentity.from_run_id(run_id or UUID("12345678-1234-5678-9234-567812345678"))
    passport = build_complete_fixture(identity)
    selected = (
        SCENARIOS
        if scenario_ids is None
        else [scenario for scenario in SCENARIOS if scenario.scenario_id in scenario_ids]
    )
    if scenario_ids is not None and tuple(item.scenario_id for item in selected) != scenario_ids:
        raise ValueError("scenario_ids must name supported scenarios in canonical order")

    results: list[ScenarioResult] = []
    for scenario in selected:
        required = (
            scenario.group,
            scenario.purpose,
            scenario.operation.get("public_api"),
            scenario.operation.get("display"),
            scenario.expected_behavior,
            scenario.explanation,
            scenario.why_it_matters,
        )
        if not all(required):
            raise AssertionError(f"{scenario.scenario_id} has incomplete teaching metadata")
        started = perf_counter()
        try:
            outcome = scenario.run(identity, passport)
        except Exception as exc:  # noqa: BLE001 - scenario boundary reports unexpected failures
            results.append(
                ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    name=scenario.name,
                    category="SDK_LOCAL",
                    status=ScenarioStatus.FAILED,
                    duration_seconds=perf_counter() - started,
                    summary="Scenario raised an unexpected exception",
                    details=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        results.append(
            ScenarioResult(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                category="SDK_LOCAL",
                status=(
                    ScenarioStatus.EXPECTED_ERROR
                    if scenario.expected_error
                    else ScenarioStatus.PASSED
                ),
                duration_seconds=perf_counter() - started,
                summary=outcome.summary,
                details=json.dumps(outcome.observed_result, sort_keys=True),
                teaching=ScenarioTeaching(
                    group=scenario.group,
                    evidence_class="SDK_LOCAL",
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
