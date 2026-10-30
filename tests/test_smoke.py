"""Public package imports and intentional API boundary checks."""

import dpp_sdk
import dpp_sdk.clients as clients
import dpp_sdk.core as core
import dpp_sdk.dpp4fun as dpp4fun


def test_package_version() -> None:
    assert isinstance(dpp_sdk.__version__, str)
    assert "__version__" in dpp_sdk.__all__


def test_all_declared_exports_resolve_and_match_their_packages() -> None:
    for package in (dpp_sdk, clients, core, dpp4fun):
        assert len(package.__all__) == len(set(package.__all__))
        assert all(hasattr(package, name) for name in package.__all__)

    for name in clients.__all__:
        assert hasattr(clients, name)
    for name in core.__all__:
        assert hasattr(core, name)
    for name in dpp4fun.__all__:
        assert hasattr(dpp4fun, name)
    for name in (
        "Dpp4FunElementDefinition",
        "Dpp4FunQuantity",
        "Dpp4FunSemanticProfile",
    ):
        assert name in dpp4fun.__all__


def test_obsolete_compatibility_apis_are_absent() -> None:
    for package in (dpp_sdk, core):
        for name in ("Dpp", "DppCore", "PassportMetadata", "validate_dpp_core"):
            assert not hasattr(package, name)
    for name in (
        "DppCodec",
        "DppValidator",
        "DppValidationClientError",
        "UpdateDataElementRequest",
        "local_repo_base_url",
        "local_registry_base_url",
    ):
        assert not hasattr(clients, name)
    assert not hasattr(dpp4fun, "ProductClassification")
    for name in ("ProfileDefinition", "SemanticProfile", "SemanticQuantity"):
        assert not hasattr(dpp4fun, name)


def test_subpackages_importable() -> None:
    import dpp_sdk.clients  # noqa: F401
    import dpp_sdk.core  # noqa: F401
    import dpp_sdk.dpp4fun  # noqa: F401
