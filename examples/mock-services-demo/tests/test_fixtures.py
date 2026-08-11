from __future__ import annotations

from uuid import UUID

from dpp_sdk import Dpp4Fun, validate_dpp4fun

from dpp_mock_services_demo.fixtures import (
    DemoIdentity,
    build_complete_fixture,
    build_minimal_fixture,
    new_demo_identity,
)


def test_identity_is_unique_per_run_and_repeatable_for_a_run_id() -> None:
    first = new_demo_identity()
    second = new_demo_identity()
    fixed_run = UUID("12345678-1234-5678-9234-567812345678")

    assert first.dpp_id != second.dpp_id
    assert first.product_id != second.product_id
    assert first.registry_sensitive_id != second.registry_sensitive_id
    assert DemoIdentity.from_run_id(fixed_run) == DemoIdentity.from_run_id(fixed_run)


def test_minimal_fixture_is_typed_valid_and_uses_run_identity() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    fixture = build_minimal_fixture(identity)

    assert isinstance(fixture, Dpp4Fun)
    assert fixture.dpp_id == str(identity.dpp_id)
    assert fixture.product_id == identity.product_id
    assert fixture.documentation is None
    assert fixture.billOfMaterials is None
    validate_dpp4fun(fixture)


def test_complete_fixture_populates_every_optional_group_with_tuples() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    fixture = build_complete_fixture(identity)

    assert fixture.documentation is not None
    assert fixture.manufacturer is not None
    assert fixture.manufacturer.contact is not None
    assert fixture.manufacturer.contact.address is not None
    assert fixture.manufacturer.contact.email is not None
    assert fixture.manufacturer.contact.telephone is not None
    assert fixture.billOfMaterials is not None
    assert isinstance(fixture.tags, tuple)
    assert isinstance(fixture.features, tuple)
    assert isinstance(fixture.billOfMaterials.materials, tuple)
    assert fixture.billOfMaterials.components
    assert fixture.billOfMaterials.parts
    validate_dpp4fun(fixture)
