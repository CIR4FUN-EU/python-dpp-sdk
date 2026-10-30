"""Installed-wheel client proof using canonical JSON and public SDK interfaces."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx

import dpp_sdk
from dpp_sdk import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    DppJsonCodec,
    Granularity,
    SingleValuedDataElement,
)
from dpp_sdk.clients import (
    DppMappingClientError,
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    RegisterDppRequest,
)
from dpp_sdk.dpp4fun import Dpp4Fun, Dpp4FunJsonCodec, Nameplate


def main() -> None:
    module_path = Path(dpp_sdk.__file__).resolve()
    assert "site-packages" in str(module_path).lower()
    assert "DigitalProductPassport" in dpp_sdk.__all__
    assert "Dpp4FunJsonCodec" in dpp_sdk.__all__

    header = DppHeader(
        digital_product_passport_id="11111111-1111-1111-1111-111111111111",
        unique_product_identifier="urn:example:product:wheel-test",
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 2, tzinfo=UTC),
        economic_operator_id="urn:example:operator:wheel-test",
    )
    core = DigitalProductPassport(
        dpp_header=header,
        elements=(
            SingleValuedDataElement(
                element_id="name",
                object_type="SingleValuedDataElement",
                value="Installed Wheel Furniture",
            ),
            DataElementCollection(
                element_id="extension",
                elements=(
                    SingleValuedDataElement(
                        element_id="opaqueValue", object_type="SingleValuedDataElement", value=7
                    ),
                ),
            ),
        ),
    )
    core_codec = DppJsonCodec()
    core_json = core_codec.to_expanded_json(core)
    assert core_codec.to_expanded_json(core_codec.from_expanded_json(core_json)) == core_json

    dpp4fun = Dpp4Fun.create(header, Nameplate.create(manufacturerName="Wheel Manufacturer"))
    dpp4fun_codec = Dpp4FunJsonCodec()
    dpp4fun_full = dpp4fun_codec.to_expanded_json(dpp4fun)
    dpp4fun_compressed = dpp4fun_codec.to_compressed_json(dpp4fun)
    restored_dpp4fun = dpp4fun_codec.from_compressed_json(dpp4fun_compressed)
    passport = json.loads(dpp4fun_full)
    assert dpp4fun_codec.to_expanded_json(restored_dpp4fun) == dpp4fun_full
    serialized = json.dumps(passport, separators=(",", ":"))
    repository_requests: list[str] = []
    history_date = datetime(2024, 1, 2, 4, 4, 5, tzinfo=timezone(timedelta(hours=1)))
    history_path = (
        b"/v1/dppsByIdAndDate/DPP%7E1%3F%23?date=2024-01-02T03%3A04%3A05Z&representation=full"
    )

    def repository_handler(request: httpx.Request) -> httpx.Response:
        raw_path = request.url.raw_path
        repository_requests.append(f"{request.method} {raw_path.decode()}")
        if request.method == "POST":
            assert raw_path == b"/v1/dpps"
            assert request.content.decode() == serialized
            return httpx.Response(
                201,
                json={
                    "statusCode": "SuccessCreated",
                    "payload": {"digitalProductPassportId": "DPP~1?#"},
                },
            )
        if raw_path == history_path:
            assert request.method == "GET"
            return httpx.Response(
                200, json={"statusCode": "Success", "payload": json.loads(serialized)}
            )
        assert raw_path == b"/v1/dpps/mapping-error"
        return httpx.Response(200, json={"statusCode": "Success", "payload": None})

    with httpx.Client(transport=httpx.MockTransport(repository_handler)) as http_client:
        repository = DppRepoClient("https://repo.example", client=http_client)
        created = repository.create_dpp(passport)
        assert created.digital_product_passport_id == "DPP~1?#"
        history = repository.read_dpp_version_by_id_and_date(
            "DPP~1?#", history_date, DppRepresentation.FULL
        )
        assert history.payload == passport
        empty_response = repository.read_dpp_by_id("mapping-error")
        assert empty_response.payload is None
        assert not http_client.is_closed

    partial_requests: list[bytes] = []

    def partial_handler(request: httpx.Request) -> httpx.Response:
        partial_requests.append(request.content)
        if request.url.raw_path == b"/v1/dpps/partial":
            return httpx.Response(
                200, json={"statusCode": "Success", "payload": json.loads(serialized)}
            )
        assert request.url.raw_path == b"/v1/dpps/partial/elements/%24.productName"
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    with httpx.Client(transport=httpx.MockTransport(partial_handler)) as http_client:
        repository = DppRepoClient("https://repo.example", client=http_client)
        updated = repository.update_dpp_by_id("partial", {"weight": 2.5})
        assert updated.payload == passport
        element = repository.update_data_element("partial", "$.productName", "updated")
        assert element.payload == {"accepted": True}
        for operation, invalid, cause_type in (
            (repository.update_dpp_by_id, float("nan"), ValueError),
            (
                lambda dpp_id, value: repository.update_data_element(
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
    assert partial_requests == [b'{"weight":2.5}', b'"updated"']

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
            200, json={"statusCode": "Success", "payload": {"registrationId": "REG-1"}}
        )

    registry_request = RegisterDppRequest(
        unique_product_identifier="11111111-1111-1111-1111-111111111111",
        digital_product_passport_id="DPP~1?#",
        unique_economic_operator_identifier="OP-1",
        dpp_api_endpoint="https://repo.example/v1/dpps",
    )
    with httpx.Client(transport=httpx.MockTransport(registry_handler)) as http_client:
        registry = DppRegistryClient("https://registry.example", client=http_client)
        assert registry.post_new_dpp_to_registry(registry_request).registration_id == "REG-1"
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
                "domain_roundtrips": ["core", "dpp4fun"],
                "status": "PASSED",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
