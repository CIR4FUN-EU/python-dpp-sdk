"""Opt-in live checks using neutral JSON and externally configured API URLs."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from dpp_sdk.clients import DppRegistryClient, DppRepoClient, RegisterDppRequest

pytestmark = pytest.mark.integration


def _base_url(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    if not value:
        pytest.skip(f"{name} is empty")
    return value


def _passport() -> dict[str, object]:
    return {
        "dpp_header": {
            "digitalProductPassportId": str(uuid4()),
            "uniqueProductIdentifier": f"urn:example:product:{uuid4()}",
            "granularity": "item",
            "dppSchemaVersion": "1.0",
            "dppStatus": "active",
            "lastUpdated": "2026-01-01T00:00:00Z",
            "economicOperatorId": "urn:example:operator:1",
        },
        "elements": [],
    }


def test_repository_json_lifecycle_against_external_endpoint() -> None:
    base = _base_url("DPP_REPO_BASE_URL", "http://localhost:8080")
    passport = _passport()
    identifier = passport["dpp_header"]["digitalProductPassportId"]  # type: ignore[index]
    with DppRepoClient(base) as repo:
        created = repo.create_dpp(passport)
        assert created.digital_product_passport_id
        try:
            read = repo.read_dpp_by_id(str(identifier))
            assert read.payload["dpp_header"]["digitalProductPassportId"] == identifier
            ids = repo.read_dpp_ids_by_product_ids(
                [passport["dpp_header"]["uniqueProductIdentifier"]]  # type: ignore[index]
            )
            assert str(identifier) in ids.dpp_identifiers
        finally:
            repo.delete_dpp_by_id(str(identifier))


def test_registry_registration_against_external_endpoint() -> None:
    registry_base = _base_url("DPP_REGISTRY_BASE_URL", "http://localhost:8081")
    repo_base = _base_url("DPP_REPO_BASE_URL", "http://localhost:8080")
    request = RegisterDppRequest(
        unique_product_identifier="urn:example:product:1",
        digital_product_passport_id="urn:example:dpp:1",
        unique_economic_operator_identifier="urn:example:operator:1",
        dpp_api_endpoint=repo_base,
    )
    with DppRegistryClient(registry_base) as registry:
        assert registry.post_new_dpp_to_registry(request).registration_id
