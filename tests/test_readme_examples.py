"""No-network examples kept in lockstep with the README's public guidance."""

from __future__ import annotations

import json
from pathlib import Path

from dpp_sdk import Dpp4Fun, from_json, to_json, validate_dpp4fun
from dpp_sdk.clients import (
    RegisterDppRequest,
    RegisterDppResponse,
    UpdateDataElementRequest,
)

README = Path(__file__).parents[1] / "README.md"


def test_readme_documents_current_model_and_client_contracts() -> None:
    readme = README.read_text(encoding="utf-8")
    for required_text in (
        "fail-fast",
        "with_updates",
        "immutable tuples",
        "POST /v1/registerDPP",
        "read_compressed_dpp_by_id",
        "read_dpp_version_by_id_and_date",
        "legacy compatibility only",
        "DppMappingClientError",
        "caller-owned",
        "UpdateDataElementRequest",
    ):
        assert required_text in readme
    assert 'dppApiEndpoint="https://repo.example.com"' in readme
    assert "dppApiEndpoint=local_repo_base_url()" not in readme


def test_readme_model_example_uses_immutable_updates_and_json_arrays(
    valid_dpp4fun: Dpp4Fun,
) -> None:
    # README: validate explicitly, update immutably, then use the normal codec.
    validate_dpp4fun(valid_dpp4fun)
    updated = valid_dpp4fun.with_updates(
        characteristics=valid_dpp4fun.characteristics.with_updates(productName="ErgoChair Pro 2")
    )
    validate_dpp4fun(updated)

    assert updated is not valid_dpp4fun
    assert valid_dpp4fun.characteristics.productName == "ErgoChair Pro"
    assert isinstance(updated.classification.tags, tuple)
    assert json.loads(to_json(updated))["classification"]["tags"] == ["ergonomic", "adjustable"]
    assert from_json(to_json(updated)) == updated


def test_readme_registry_example_emits_canonical_names_without_network() -> None:
    request = RegisterDppRequest(
        uniqueProductIdentifier="GTIN-0001",
        digitalProductPassportId="DPP-1",
        uniqueEconomicOperatorIdentifier="operator-123",
        dppApiEndpoint="https://repo.example.com",
    )
    response = RegisterDppResponse(registrationId="REG-1")

    assert request.model_dump() == {
        "uniqueProductIdentifier": "GTIN-0001",
        "digitalProductPassportId": "DPP-1",
        "uniqueEconomicOperatorIdentifier": "operator-123",
        "dppApiEndpoint": "https://repo.example.com",
    }
    assert response.registrationId == "REG-1"
    assert UpdateDataElementRequest(payload=None).payload is None
