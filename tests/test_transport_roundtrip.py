"""JSON transport: flat outbound, flat-or-nested inbound, and edge cases."""

from __future__ import annotations

import json

from dpp_sdk.dpp4fun.model import Dpp4Fun
from dpp_sdk.dpp4fun.transport import from_json, from_json_and_validate, to_json

_CORE_KEYS = {"passportMetadata", "nameplate", "documentation"}


def test_outbound_is_flattened(valid_dpp4fun: Dpp4Fun) -> None:
    data = json.loads(to_json(valid_dpp4fun))
    assert "coreDpp" not in data
    assert data.keys() >= _CORE_KEYS
    assert {"classification", "characteristics", "billOfMaterials"} <= data.keys()


def test_outbound_key_order_matches_java(valid_dpp4fun: Dpp4Fun) -> None:
    keys = list(json.loads(to_json(valid_dpp4fun)).keys())
    assert keys == [
        "classification",
        "characteristics",
        "billOfMaterials",
        "passportMetadata",
        "nameplate",
        "documentation",
    ]


def test_round_trip_from_flat(valid_dpp4fun: Dpp4Fun) -> None:
    assert from_json(to_json(valid_dpp4fun)) == valid_dpp4fun


def test_round_trip_from_nested(valid_dpp4fun: Dpp4Fun) -> None:
    nested = json.dumps(valid_dpp4fun.model_dump(mode="json"))
    assert from_json(nested) == valid_dpp4fun


def test_nested_takes_precedence_over_duplicate_flat_keys(valid_dpp4fun: Dpp4Fun) -> None:
    nested = valid_dpp4fun.model_dump(mode="json")
    # Add a stray flat key alongside coreDpp; normalize should drop it.
    nested["nameplate"] = {"gtinCode": "SHOULD-BE-DROPPED"}
    parsed = from_json(json.dumps(nested))
    assert parsed.gtinCode == valid_dpp4fun.gtinCode


def test_empty_lists_serialized_not_null(valid_dpp4fun: Dpp4Fun) -> None:
    minimal = valid_dpp4fun.model_copy(
        update={"classification": valid_dpp4fun.classification.model_copy(update={"tags": []})}
    )
    data = json.loads(to_json(minimal))
    assert data["classification"]["tags"] == []
    assert data["characteristics"]["features"] == ["lumbar-support"]


def test_from_json_and_validate(valid_dpp4fun: Dpp4Fun) -> None:
    assert from_json_and_validate(to_json(valid_dpp4fun)) == valid_dpp4fun


def test_codec_is_usable_as_dpp_codec(valid_dpp4fun: Dpp4Fun) -> None:
    from dpp_sdk.dpp4fun.transport import Dpp4FunJsonCodec

    codec = Dpp4FunJsonCodec()
    assert codec.from_json(codec.to_json(valid_dpp4fun)) == valid_dpp4fun
