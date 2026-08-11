"""JSON transport: flat outbound, flat-or-nested inbound, and edge cases."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from dpp_sdk.core.errors import DppMappingError
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
    minimal = valid_dpp4fun.with_updates(
        classification=valid_dpp4fun.classification.with_updates(tags=[])
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


@pytest.mark.parametrize(
    "contract_id",
    [pytest.param("CODEC-MALFORMED-JSON-001", id="CODEC-MALFORMED-JSON-001")],
)
def test_malformed_json_is_mapping_error_with_syntax_cause(contract_id: str) -> None:
    with pytest.raises(DppMappingError) as exc:
        from_json("{not-json")
    assert isinstance(exc.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "contract_id",
    [pytest.param("MAPPING-DOMAIN-PAYLOAD-001", id="MAPPING-DOMAIN-PAYLOAD-001")],
)
def test_structurally_unmappable_json_is_mapping_error_with_pydantic_cause(
    contract_id: str,
) -> None:
    with pytest.raises(DppMappingError) as exc:
        from_json('{"classification": {}}')
    assert isinstance(exc.value.__cause__, ValidationError)


@pytest.mark.parametrize(
    ("raw", "cause_type"),
    [
        pytest.param("null", ValidationError, id="null"),
        pytest.param("", json.JSONDecodeError, id="missing-root"),
        pytest.param("{}", ValidationError, id="empty-object"),
    ],
)
def test_dec_004_standalone_invalid_roots_are_causal_mapping_failures(
    raw: str,
    cause_type: type[Exception],
) -> None:
    with pytest.raises(DppMappingError) as exc:
        from_json(raw)

    assert isinstance(exc.value.__cause__, cause_type)


@pytest.mark.parametrize(
    ("field", "members", "path"),
    [
        pytest.param("features", [None, "valid"], "characteristics.features.0", id="null-first"),
        pytest.param("tags", ["valid", None], "classification.tags.1", id="null-later"),
    ],
)
def test_dec_001_null_string_list_member_is_causal_mapping_failure(
    valid_dpp4fun: Dpp4Fun,
    field: str,
    members: list[str | None],
    path: str,
) -> None:
    payload = json.loads(to_json(valid_dpp4fun))
    owner = "characteristics" if field == "features" else "classification"
    payload[owner][field] = members

    with pytest.raises(DppMappingError) as exc:
        from_json(json.dumps(payload))

    assert isinstance(exc.value.__cause__, ValidationError)
    assert path in str(exc.value.__cause__)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_dec_003_non_finite_json_input_is_causal_mapping_failure(
    valid_dpp4fun: Dpp4Fun,
    token: str,
) -> None:
    payload = to_json(valid_dpp4fun).replace('"weight": 14.5', f'"weight": {token}')

    with pytest.raises(DppMappingError) as exc:
        from_json(payload)

    assert exc.value.__cause__ is not None


def test_dec_003_finite_exponent_json_is_accepted(valid_dpp4fun: Dpp4Fun) -> None:
    payload = to_json(valid_dpp4fun).replace('"weight": 14.5', '"weight": 1.45e1')
    assert from_json(payload).weight == 14.5


def test_dec_003_non_finite_output_is_causal_mapping_failure(
    valid_dpp4fun: Dpp4Fun,
) -> None:
    invalid_characteristics = valid_dpp4fun.characteristics.model_copy(
        update={"weight": float("inf")}
    )
    invalid = valid_dpp4fun.model_copy(update={"characteristics": invalid_characteristics})

    with pytest.raises(DppMappingError) as exc:
        to_json(invalid)

    assert isinstance(exc.value.__cause__, ValueError)
