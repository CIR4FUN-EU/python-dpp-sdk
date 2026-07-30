"""Opt-in live conformance tests for externally supplied repository endpoints.

The suite auto-skips unless both configured endpoints answer ``GET /health``.
It covers create, reads, curated-element update, delete, and registry registration;
a fresh DPP identifier keeps the interaction idempotent.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from dpp_sdk.clients import (
    DppRegistryClient,
    DppRepoClient,
    RegisterDppRequest,
    local_repo_base_url,
)
from dpp_sdk.dpp4fun import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.dpp4fun.model import Dpp4Fun

pytestmark = pytest.mark.integration


@pytest.fixture
def repo_client() -> DppRepoClient[Dpp4Fun]:
    client: DppRepoClient[Dpp4Fun] = DppRepoClient.for_local_mock(
        Dpp4FunJsonCodec(), validate_dpp4fun
    )
    if not client.health_check():
        pytest.skip("repository endpoint is unavailable")
    return client


@pytest.fixture
def registry_client() -> DppRegistryClient:
    client = DppRegistryClient.for_local_mock()
    if not client.health_check():
        pytest.skip("registry endpoint is unavailable")
    return client


def _with_fresh_dpp_id(dpp: Dpp4Fun) -> Dpp4Fun:
    """Return a copy with a new ``uniqueProductIdentifier`` (drives ``dpp_id``)."""
    meta = dpp.coreDpp.passportMetadata.with_updates(uniqueProductIdentifier=uuid4())
    core = dpp.coreDpp.with_updates(passportMetadata=meta)
    return dpp.with_updates(coreDpp=core)


def test_repo_lifecycle_against_external_endpoint(
    repo_client: DppRepoClient[Dpp4Fun], valid_dpp4fun: Dpp4Fun
) -> None:
    dpp = _with_fresh_dpp_id(valid_dpp4fun)
    dpp_id = dpp.dpp_id
    product_id = dpp.product_id

    created = repo_client.create_dpp(dpp)
    assert created.dppId

    try:
        assert repo_client.read_dpp_by_id(dpp_id).dpp_id == dpp_id
        assert repo_client.read_dpp_by_product_id(product_id).product_id == product_id

        # Fine-granular read/update against the curated element path.
        assert (
            repo_client.read_data_element(dpp_id, "$.characteristics.productName")
            == dpp.productName
        )
        updated = repo_client.update_data_element(
            dpp_id, "$.characteristics.productName", "Updated via live test"
        )
        assert updated == "Updated via live test"

        ids = repo_client.read_dpp_ids_by_product_ids([product_id], limit=10)
        assert ids.dppIdentifiers is not None
        assert dpp_id in ids.dppIdentifiers
    finally:
        repo_client.delete_dpp_by_id(dpp_id)


def test_registry_register_against_external_endpoint(
    repo_client: DppRepoClient[Dpp4Fun],
    registry_client: DppRegistryClient,
    valid_dpp4fun: Dpp4Fun,
) -> None:
    # The registry verifies the repo reference via HEAD, so the DPP must exist first.
    dpp = _with_fresh_dpp_id(valid_dpp4fun)
    dpp_id = dpp.dpp_id
    repo_client.create_dpp(dpp)
    try:
        response = registry_client.post_new_dpp_to_registry(
            RegisterDppRequest(
                uniqueProductIdentifier=dpp.product_id,
                digitalProductPassportId=dpp_id,
                uniqueEconomicOperatorIdentifier="operator-123",
                dppApiEndpoint=local_repo_base_url(),
            )
        )
        assert response.registrationId
    finally:
        repo_client.delete_dpp_by_id(dpp_id)
