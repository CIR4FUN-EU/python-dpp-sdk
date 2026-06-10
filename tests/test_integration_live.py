"""Live conformance test against the Java mock services (``dpp-sdk-demo``).

Auto-skips unless both the mock repo (``http://localhost:8080``) and the mock registry
(``http://localhost:8081``) answer ``GET /health``. Start them first, e.g. from
``../dpp-sdk-platform/dpp-sdk-demo`` (``docker compose up`` or the two Spring
``mvnw spring-boot:run`` modules), then run ``pytest -m integration``.

Mirrors ``HttpServiceDemoRunner.run``: create -> read-by-id -> read-by-product-id ->
fine-granular read/update -> delete, plus a registry registration. A fresh DPP id is
used per run so the flow is idempotent.
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
from dpp_sdk.dpp4fun.model import Dpp4Fun
from dpp_sdk.dpp4fun.transport import Dpp4FunJsonCodec, validate_dpp4fun

pytestmark = pytest.mark.integration


@pytest.fixture
def repo_client() -> DppRepoClient[Dpp4Fun]:
    client: DppRepoClient[Dpp4Fun] = DppRepoClient.for_local_mock(
        Dpp4FunJsonCodec(), validate_dpp4fun
    )
    if not client.health_check():
        pytest.skip("mock-dpp-repo not running on its local endpoint")
    return client


@pytest.fixture
def registry_client() -> DppRegistryClient:
    client = DppRegistryClient.for_local_mock()
    if not client.health_check():
        pytest.skip("mock-eu-registry not running on its local endpoint")
    return client


def _with_fresh_dpp_id(dpp: Dpp4Fun) -> Dpp4Fun:
    """Return a copy with a new ``uniqueProductIdentifier`` (drives ``dpp_id``)."""
    meta = dpp.coreDpp.passportMetadata.model_copy(
        update={"uniqueProductIdentifier": uuid4()}
    )
    core = dpp.coreDpp.model_copy(update={"passportMetadata": meta})
    return dpp.model_copy(update={"coreDpp": core})


def test_repo_lifecycle_against_mock(
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

        # Fine-granular read/update against the curated element path the mock supports.
        assert (
            repo_client.read_data_element(dpp_id, "characteristics.productName")
            == dpp.productName
        )
        updated = repo_client.update_data_element(
            dpp_id, "characteristics.productName", "Updated via live test"
        )
        assert updated == "Updated via live test"

        ids = repo_client.read_dpp_ids_by_product_ids([product_id], limit=10)
        assert dpp_id in ids.dppIdentifiers
    finally:
        repo_client.delete_dpp_by_id(dpp_id)


def test_registry_register_against_mock(
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
                productIdentifier=dpp.product_id,
                dppIdentifier=dpp_id,
                operatorIdentifier="operator-123",
                repoUrl=local_repo_base_url(),
            )
        )
        assert response.registryIdentifier
    finally:
        repo_client.delete_dpp_by_id(dpp_id)
