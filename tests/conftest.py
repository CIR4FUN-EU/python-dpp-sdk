"""Shared pytest fixtures (port of TestDataFactory / CoreTestDataFactory)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from dpp_sdk.core.model import (
    Address,
    Contact,
    Documentation,
    DppCore,
    Email,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
)
from dpp_sdk.dpp4fun.model import (
    BillOfMaterials,
    Characteristics,
    Dimensions,
    Dpp4Fun,
    Material,
    ProductClassification,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    try:
        parser.addoption(
            "--run-java-services",
            action="store_true",
            default=False,
            help=(
                "run integration tests against already-running Java "
                "repository and registry services"
            ),
        )
    except ValueError as exc:
        if "--run-java-services" not in str(exc):
            raise


@pytest.fixture(autouse=True)
def require_java_services_for_integration(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> None:
    """Block every integration-marked test before it can construct a live client."""
    if request.node.get_closest_marker("integration") and not pytestconfig.getoption(
        "--run-java-services"
    ):
        pytest.skip("requires --run-java-services and running Java services")


@pytest.fixture
def manufacturer() -> Organization:
    return Organization(
        name="ACME Furniture GmbH",
        gln="4012345000009",
        role=OrganizationRole.MANUFACTURER,
        contact=Contact(
            organization="ACME HQ",
            address=Address(country="DE", town="Berlin", street="Hauptstr. 1", zipCode="10115"),
            email=Email(emailAddress="info@acme.example", typeOfEmail="business"),
        ),
    )


@pytest.fixture
def valid_core(manufacturer: Organization) -> DppCore:
    return DppCore(
        passportMetadata=PassportMetadata(
            uniqueProductIdentifier=UUID("11111111-1111-1111-1111-111111111111"),
            passportUpdateDates=[date(2024, 1, 1)],
            qrCodeOrDigitalTag="QR-001",
        ),
        nameplate=Nameplate(
            gtinCode="GTIN-0001",
            internalArticleNumber="ART-1",
            manufacturer=manufacturer,
        ),
        documentation=Documentation(
            digitalInstructionsLink="https://acme.example/docs",
            downloadable=True,
            availableForYears=10,
        ),
    )


@pytest.fixture
def valid_dpp4fun(valid_core: DppCore) -> Dpp4Fun:
    return Dpp4Fun(
        coreDpp=valid_core,
        classification=ProductClassification(
            sector="Furniture",
            category="Office Chair",
            group="Seating",
            tags=["ergonomic", "adjustable"],
        ),
        characteristics=Characteristics(
            productName="ErgoChair Pro",
            productType="Office Chair",
            brand="ACME",
            dimensions=Dimensions(width=60.0, height=120.0, depth=60.0, unit="cm"),
            weight=14.5,
            features=["lumbar-support"],
        ),
        billOfMaterials=BillOfMaterials(
            materials=[
                Material(name="steel", mandatory=True, portion=0.6, reference="MAT-STEEL"),
                Material(name="foam", portion=0.4),
            ],
        ),
    )
