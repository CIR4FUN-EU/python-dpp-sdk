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
MODULE_READMES = {
    "core": README.parent / "src" / "dpp_sdk" / "core" / "README.md",
    "dpp4fun": README.parent / "src" / "dpp_sdk" / "dpp4fun" / "README.md",
    "clients": README.parent / "src" / "dpp_sdk" / "clients" / "README.md",
}


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
        "## Standards alignment",
        "EN 18222:2026",
        "not a formal compliance implementation",
        "## Known standards limitations",
        "project-defined",
        "complete generic implementation of RFC 7396 JSON Merge Patch",
        "complete implementation of RFC 9535 JSONPath",
        "does not record lifecycle events",
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


def test_module_readmes_have_single_owner_links_and_root_build_commands() -> None:
    required_text = {
        "core": (
            "# DPP SDK core module",
            "validate_dpp_core()",
            "python -m build",
            "tests/test_core_model.py tests/test_core_validation.py",
            "not separately built or",
        ),
        "dpp4fun": (
            "# DPP SDK DPP4Fun module",
            "Dpp4FunJsonCodec",
            "python -m build",
            "tests/test_dpp4fun_validation.py tests/test_transport_roundtrip.py",
            "not a separately buildable or",
        ),
        "clients": (
            "# DPP SDK clients module",
            "DppRepoClient[T]",
            "python -m build",
            "tests/test_clients.py tests/test_end_to_end.py",
            "not a separately buildable or",
        ),
    }

    for module, expected in required_text.items():
        content = MODULE_READMES[module].read_text(encoding="utf-8")
        for text in expected:
            assert text in content
