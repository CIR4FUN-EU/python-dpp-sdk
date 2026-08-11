"""Smoke test confirming the package imports and the scaffold is wired correctly.

Replace/extend as real modules land. The full suite should mirror the Java tests in
the maintained SDK contract (round-trip, edge cases, inbound validation, end-to-end scenarios).
"""

import pytest

import dpp_sdk
import dpp_sdk.clients as clients
import dpp_sdk.core as core
import dpp_sdk.dpp4fun as dpp4fun
from dpp_sdk.clients import (
    CreateDppResponse,
    DeleteDppResponse,
    DppCodec,
    DppRegistryClient,
    DppRepoClient,
    DppValidator,
    ReadDppIdsRequest,
    ReadDppIdsResponse,
    RegisterDppRequest,
    RegisterDppResponse,
    UpdateDataElementRequest,
)
from dpp_sdk.core import (
    Address,
    Contact,
    Documentation,
    Dpp,
    DppCore,
    Email,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    Telephone,
)
from dpp_sdk.dpp4fun import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Material,
    Part,
    ProductClassification,
)


def test_package_version() -> None:
    assert isinstance(dpp_sdk.__version__, str)
    assert dpp_sdk.__version__.count(".") >= 2
    assert "__version__" in dpp_sdk.__all__


@pytest.mark.parametrize(
    "contract_id",
    ["EXPORT-PUBLIC-CLIENTS-001", "EXPORT-PUBLIC-CORE-001", "EXPORT-PUBLIC-DPP4FUN-001"],
)
def test_curated_exports_resolve_from_their_owning_packages(contract_id: str) -> None:
    client_exports = {
        "CreateDppResponse": CreateDppResponse,
        "DeleteDppResponse": DeleteDppResponse,
        "DppCodec": DppCodec,
        "DppRegistryClient": DppRegistryClient,
        "DppRepoClient": DppRepoClient,
        "DppValidator": DppValidator,
        "ReadDppIdsRequest": ReadDppIdsRequest,
        "ReadDppIdsResponse": ReadDppIdsResponse,
        "RegisterDppRequest": RegisterDppRequest,
        "RegisterDppResponse": RegisterDppResponse,
        "UpdateDataElementRequest": UpdateDataElementRequest,
    }
    core_exports = {
        "Address": Address,
        "Contact": Contact,
        "Documentation": Documentation,
        "Dpp": Dpp,
        "DppCore": DppCore,
        "Email": Email,
        "Nameplate": Nameplate,
        "Organization": Organization,
        "OrganizationRole": OrganizationRole,
        "PassportMetadata": PassportMetadata,
        "Telephone": Telephone,
    }
    dpp4fun_exports = {
        "BillOfMaterials": BillOfMaterials,
        "Characteristics": Characteristics,
        "Component": Component,
        "Dimensions": Dimensions,
        "Dpp4Fun": Dpp4Fun,
        "Material": Material,
        "Part": Part,
        "ProductClassification": ProductClassification,
    }

    for name, symbol in client_exports.items():
        assert getattr(clients, name) is symbol
        assert name in clients.__all__
    for name, symbol in core_exports.items():
        assert getattr(core, name) is symbol
        assert name in core.__all__
    for name, symbol in dpp4fun_exports.items():
        assert getattr(dpp4fun, name) is symbol
        assert name in dpp4fun.__all__

    assert dpp_sdk.Dpp4Fun is Dpp4Fun
    assert not hasattr(dpp_sdk, "DppRepoClient")


def test_subpackages_importable() -> None:
    import dpp_sdk.clients  # noqa: F401
    import dpp_sdk.core  # noqa: F401
    import dpp_sdk.dpp4fun  # noqa: F401
