"""End-to-end: build -> validate -> serialize -> parse+validate -> identifiers."""

from __future__ import annotations

from dpp_sdk import (
    Dpp4Fun,
    from_json_and_validate,
    to_json,
    validate_dpp4fun,
)


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
