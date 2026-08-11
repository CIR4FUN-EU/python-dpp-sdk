"""Installed-wheel cross-component proof using only public SDK interfaces."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from pydantic import ValidationError

import dpp_sdk
from dpp_sdk import (
    BillOfMaterials,
    Characteristics,
    Dpp4Fun,
    Dpp4FunJsonCodec,
    DppCore,
    DppValidationError,
    Material,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    ProductClassification,
    from_json,
    to_json,
    validate_dpp4fun,
)
from dpp_sdk.clients import (
    DppMappingClientError,
    DppRegistryClient,
    DppRepoClient,
    RegisterDppRequest,
)


def _valid_dpp() -> Dpp4Fun:
    manufacturer = Organization(
        name="Installed Wheel Furniture",
        role=OrganizationRole.MANUFACTURER,
    )
    core = DppCore(
        passportMetadata=PassportMetadata(
            uniqueProductIdentifier="11111111-1111-1111-1111-111111111111",
            passportUpdateDates=(date(2024, 1, 1),),
        ),
        nameplate=Nameplate(
            gtinCode="GTIN-INSTALLED-1",
            manufacturer=manufacturer,
        ),
    )
    return Dpp4Fun(
        coreDpp=core,
        classification=ProductClassification(
            sector="Furniture",
            category="Office Chair",
        ),
        characteristics=Characteristics(
            productName="Installed Chair",
            productType="Office Chair",
        ),
        billOfMaterials=BillOfMaterials(
            materials=(Material(name="Steel", portion=1.0),),
        ),
    )


def main() -> None:
    module_path = Path(dpp_sdk.__file__).resolve()
    assert "site-packages" in str(module_path).lower()

    for export in (
        "Dpp4Fun",
        "Dpp4FunJsonCodec",
        "DppValidationError",
        "from_json",
        "to_json",
        "validate_dpp4fun",
    ):
        assert getattr(dpp_sdk, export) is not None
    assert issubclass(DppValidationError, Exception)

    original = _valid_dpp()
    updated = original.with_updates(
        characteristics=original.characteristics.with_updates(productName="Installed Chair 2")
    )
    assert original.characteristics.productName == "Installed Chair"
    assert updated.characteristics.productName == "Installed Chair 2"

    try:
        updated.characteristics.with_updates(productName=" ")
    except ValidationError:
        pass
    else:  # pragma: no cover - executable proof guard
        raise AssertionError("invalid immutable update did not re-run validation")

    validate_dpp4fun(updated)
    codec = Dpp4FunJsonCodec()
    serialized = codec.to_json(updated)
    assert serialized == to_json(updated)
    restored = codec.from_json(serialized)
    assert restored == updated
    assert from_json(serialized) == updated

    repository_requests: list[str] = []
    history_date = datetime(
        2024,
        1,
        2,
        4,
        4,
        5,
        tzinfo=timezone(timedelta(hours=1)),
    )
    history_path = (
        b"/v1/dppsByIdAndDate/DPP%7E1%3F%23?date=2024-01-02T03%3A04%3A05Z&representation=full"
    )

    def repository_handler(request: httpx.Request) -> httpx.Response:
        raw_path = request.url.raw_path
        repository_requests.append(f"{request.method} {raw_path.decode()}")
        if request.method == "POST":
            assert raw_path == b"/v1/dpps"
            assert request.content.decode() == serialized
            assert json.loads(request.content)["characteristics"]["productName"] == (
                "Installed Chair 2"
            )
            return httpx.Response(
                201,
                json={
                    "statusCode": "SuccessCreated",
                    "payload": {"dppId": "DPP~1?#"},
                },
            )
        if raw_path == history_path:
            assert request.method == "GET"
            return httpx.Response(
                200,
                json={"statusCode": "Success", "payload": json.loads(serialized)},
            )
        assert raw_path == b"/v1/dpps/mapping-error?representation=full"
        return httpx.Response(
            200,
            json={"statusCode": "Success", "payload": None},
        )

    with httpx.Client(transport=httpx.MockTransport(repository_handler)) as http_client:
        repository = DppRepoClient(
            "https://repo.example",
            codec=codec,
            validator=validate_dpp4fun,
            client=http_client,
        )
        assert repository.create_dpp(updated).dppId == "DPP~1?#"
        assert repository.read_dpp_version_by_id_and_date("DPP~1?#", history_date) == updated
        try:
            repository.read_dpp_by_id("mapping-error")
        except DppMappingClientError as exc:
            assert isinstance(exc.__cause__, ValueError)
            assert "payload" in str(exc)
        else:  # pragma: no cover - executable proof guard
            raise AssertionError("null repository payload escaped mapping translation")

    partial_requests: list[bytes] = []

    def partial_handler(request: httpx.Request) -> httpx.Response:
        partial_requests.append(request.content)
        if request.url.raw_path == b"/v1/dpps/partial":
            return httpx.Response(
                200,
                json={"statusCode": "Success", "payload": json.loads(serialized)},
            )
        assert request.url.raw_path == b"/v1/dpps/partial/elements/%24.productName"
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    with httpx.Client(transport=httpx.MockTransport(partial_handler)) as http_client:
        partial_repository = DppRepoClient(
            "https://repo.example",
            codec=codec,
            validator=validate_dpp4fun,
            client=http_client,
        )
        assert partial_repository.update_dpp_by_id("partial", {"weight": 2.5}) == updated
        assert partial_repository.update_data_element("partial", "$.productName", "Grüße") == {
            "accepted": True
        }
        for operation, invalid, cause_type in (
            (partial_repository.update_dpp_by_id, float("nan"), ValueError),
            (
                lambda dpp_id, value: partial_repository.update_data_element(
                    dpp_id, "$.productName", value
                ),
                object(),
                TypeError,
            ),
        ):
            try:
                operation("partial", invalid)
            except DppMappingClientError as exc:
                assert isinstance(exc.__cause__, cause_type)
                assert "before request" in str(exc)
            else:  # pragma: no cover - executable proof guard
                raise AssertionError("invalid partial JSON escaped mapping translation")
    assert partial_requests == [b'{"weight": 2.5}', b'"Gr\\u00fc\\u00dfe"']

    registry_body = (
        '{"uniqueProductIdentifier":"11111111-1111-1111-1111-111111111111",'
        '"digitalProductPassportId":"DPP~1?#",'
        '"uniqueEconomicOperatorIdentifier":"OP-1",'
        '"dppApiEndpoint":"https://repo.example/v1/dpps"}'
    )
    registry_calls = 0

    def registry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal registry_calls
        registry_calls += 1
        assert request.method == "POST"
        assert request.url.raw_path == b"/v1/registerDPP"
        assert request.content.decode() == registry_body
        return httpx.Response(
            200,
            json={"statusCode": "Success", "payload": {"registrationId": "REG-1"}},
        )

    registry_request = RegisterDppRequest(
        uniqueProductIdentifier="11111111-1111-1111-1111-111111111111",
        digitalProductPassportId="DPP~1?#",
        uniqueEconomicOperatorIdentifier="OP-1",
        dppApiEndpoint="https://repo.example/v1/dpps",
    )
    with httpx.Client(transport=httpx.MockTransport(registry_handler)) as http_client:
        registry = DppRegistryClient("https://registry.example", client=http_client)
        assert registry.post_new_dpp_to_registry(registry_request).registrationId == "REG-1"
        try:
            registry.post_new_dpp_to_registry(None)  # type: ignore[arg-type]
        except DppMappingClientError as exc:
            assert isinstance(exc.__cause__, ValueError)
            assert "before request" in str(exc)
        else:  # pragma: no cover - executable proof guard
            raise AssertionError("null registry request escaped mapping translation")
    assert registry_calls == 1

    print(
        json.dumps(
            {
                "installed_module": str(module_path),
                "repository_requests": repository_requests,
                "registry_requests": registry_calls,
                "status": "PASSED",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
