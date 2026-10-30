"""Typed DPP4Fun build, validation, canonical transport, and generic client flow."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from dpp_sdk import Dpp4Fun, Dpp4FunJsonCodec, DppHeader, Granularity, to_json, validate_dpp4fun
from dpp_sdk.clients import DppRepoClient, DppRepresentation
from dpp_sdk.dpp4fun import ChairCharacteristics, Nameplate


def _passport() -> Dpp4Fun:
    header = DppHeader(
        digital_product_passport_id="11111111-1111-1111-1111-111111111111",
        unique_product_identifier="GTIN-0001",
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="operator-123",
    )
    return Dpp4Fun.create(
        header,
        Nameplate.create(manufacturerName="ACME"),
        ChairCharacteristics.create(color="blue"),
    )


def test_full_happy_path() -> None:
    value = _passport()
    assert validate_dpp4fun(value).is_valid
    wire = to_json(value)
    restored = Dpp4FunJsonCodec().from_json_and_validate(wire)
    assert restored.passport == value.passport
    assert restored.header.digital_product_passport_id == "11111111-1111-1111-1111-111111111111"


def test_domain_mapping_stays_outside_generic_repository_client() -> None:
    value = _passport()
    nameplate = value.typed_aspect(Nameplate)
    assert nameplate is not None
    updated = value.with_updates(
        aspects=(nameplate.with_field("manufacturerName", "ACME International"),)
    )
    wire_value = json.loads(to_json(updated))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.raw_path == b"/v1/dpps"
            assert "elements" in json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "statusCode": "SuccessCreated",
                    "payload": {
                        "digitalProductPassportId": updated.header.digital_product_passport_id
                    },
                },
            )
        if request.method == "GET":
            assert (
                request.url.raw_path
                == b"/v1/dpps/11111111-1111-1111-1111-111111111111?representation=full"
            )
            return httpx.Response(
                200, json={"statusCode": "Success", "payload": json.loads(to_json(updated))}
            )
        assert request.method == "PATCH"
        assert request.url.raw_path == b"/v1/dpps/DPP-1/elements/%24.characteristics.weight"
        assert json.loads(request.content) == "updated"
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = DppRepoClient("http://repo.test", client=client)
    created = repo.create_dpp(wire_value)
    assert created.digital_product_passport_id == updated.header.digital_product_passport_id
    read = repo.read_dpp_by_id(updated.header.digital_product_passport_id, DppRepresentation.FULL)
    assert Dpp4FunJsonCodec().from_json(json.dumps(read.payload)).passport == updated.passport
    element = repo.update_data_element("DPP-1", "$.characteristics.weight", "updated")
    assert element.payload == {"accepted": True}
    assert not client.is_closed
