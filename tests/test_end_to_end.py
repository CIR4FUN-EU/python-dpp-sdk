"""End-to-end: build -> validate -> serialize -> parse+validate -> identifiers."""

from __future__ import annotations

import json

import httpx

from dpp_sdk import (
    Dpp4Fun,
    Dpp4FunJsonCodec,
    from_json_and_validate,
    to_json,
    validate_dpp4fun,
)
from dpp_sdk.clients import DppRepoClient


def test_full_happy_path(valid_dpp4fun: Dpp4Fun) -> None:
    validate_dpp4fun(valid_dpp4fun)

    wire = to_json(valid_dpp4fun)
    restored = from_json_and_validate(wire)

    assert restored == valid_dpp4fun
    assert restored.dpp_id == "11111111-1111-1111-1111-111111111111"
    assert restored.product_id == "GTIN-0001"
    assert restored.passport_type == "Dpp4Fun Furniture"
    assert restored.category == "Office Chair"
    assert restored.productName == "ErgoChair Pro"


def test_immutable_validated_model_round_trips_through_repository_client(
    valid_dpp4fun: Dpp4Fun,
) -> None:
    """The public domain, codec, and repository boundaries retain canonical values."""
    updated = valid_dpp4fun.with_updates(
        classification=valid_dpp4fun.classification.with_updates(tags=("recyclable", "durable"))
    )
    validator_calls = 0

    def validator(dpp: Dpp4Fun) -> None:
        nonlocal validator_calls
        validator_calls += 1
        validate_dpp4fun(dpp)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.raw_path == b"/v1/dpps"
            assert json.loads(request.content)["classification"]["tags"] == [
                "recyclable",
                "durable",
            ]
            return httpx.Response(
                201,
                json={"statusCode": "SuccessCreated", "payload": {"dppId": updated.dpp_id}},
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
        assert json.loads(request.content) is None
        return httpx.Response(200, json={"statusCode": "Success", "payload": {"accepted": True}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = DppRepoClient(
        "http://repo.test",
        codec=Dpp4FunJsonCodec(),
        validator=validator,
        client=client,
    )

    assert updated.classification.tags == ("recyclable", "durable")
    assert repo.create_dpp(updated).dppId == updated.dpp_id
    assert repo.read_dpp_by_id(updated.dpp_id) == updated
    assert repo.update_data_element("DPP-1", "$.characteristics.weight", None) == {"accepted": True}
    assert validator_calls == 1
    assert not client.is_closed
