"""Deterministic demo fixtures with unique identities for every run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from dpp_sdk import (
    Address,
    BillOfMaterials,
    Characteristics,
    Component,
    Contact,
    Dimensions,
    Documentation,
    Dpp4Fun,
    DppCore,
    Email,
    Material,
    Nameplate,
    Organization,
    OrganizationRole,
    Part,
    PassportMetadata,
    ProductClassification,
    Telephone,
)


@dataclass(frozen=True)
class DemoIdentity:
    """Run-scoped identifiers used by SDK and future live scenarios."""

    run_id: UUID
    dpp_id: UUID
    product_id: str
    registry_sensitive_id: str

    @classmethod
    def from_run_id(cls, run_id: UUID) -> DemoIdentity:
        token = run_id.hex
        return cls(
            run_id=run_id,
            dpp_id=run_id,
            product_id=f"C4F-PY-{token}",
            registry_sensitive_id=f"C4F-REG-{token}",
        )


def new_demo_identity() -> DemoIdentity:
    """Create a new identity suitable for repeated disposable demo runs."""

    return DemoIdentity.from_run_id(uuid4())


def _manufacturer(*, complete: bool) -> Organization:
    if not complete:
        return Organization(name="CIR4FUN Demo Manufacturer", role=OrganizationRole.MANUFACTURER)
    return Organization(
        name="CIR4FUN Demo Manufacturer",
        gln="4012345000009",
        productDescription="Deterministic Java-services demo fixture",
        productDesignation="Demo Office Chair",
        productFamily="Furniture",
        productRoot="Chair",
        productOrderSuffix="DEMO",
        uri="https://example.invalid/manufacturers/cir4fun-demo",
        role=OrganizationRole.MANUFACTURER,
        contact=Contact(
            organization="CIR4FUN Demo Support",
            address=Address(
                country="DE",
                zipCode="10115",
                region="Berlin",
                town="Berlin",
                street="Example Street 1",
            ),
            email=Email(emailAddress="support@example.invalid", typeOfEmail="business"),
            telephone=Telephone(telephoneNumber="+49-30-5550000", typeOfTelephone="business"),
        ),
    )


def build_minimal_fixture(identity: DemoIdentity) -> Dpp4Fun:
    """Build the smallest structurally and semantically valid furniture DPP."""

    return Dpp4Fun(
        coreDpp=DppCore(
            passportMetadata=PassportMetadata(
                uniqueProductIdentifier=identity.dpp_id,
                passportUpdateDates=(date(2024, 1, 1),),
            ),
            nameplate=Nameplate(
                gtinCode=identity.product_id,
                manufacturer=_manufacturer(complete=False),
            ),
        ),
        classification=ProductClassification(sector="Furniture", category="Office Chair"),
        characteristics=Characteristics(
            productName="CIR4FUN Demo Chair",
            productType="Office Chair",
        ),
    )


def build_complete_fixture(identity: DemoIdentity) -> Dpp4Fun:
    """Build a deterministic fixture with every optional model group populated."""

    return Dpp4Fun(
        coreDpp=DppCore(
            passportMetadata=PassportMetadata(
                uniqueProductIdentifier=identity.dpp_id,
                passportUpdateDates=(date(2024, 1, 1), date(2024, 6, 1)),
                qrCodeOrDigitalTag=identity.registry_sensitive_id,
                externalDocumentationLink="https://example.invalid/dpp/demo-chair",
            ),
            nameplate=Nameplate(
                gtinCode=identity.product_id,
                internalArticleNumber="C4F-DEMO-CHAIR",
                batchNumber="DEMO-BATCH-2024",
                customsTariffNumber="94013000",
                uriOfTheProduct="https://example.invalid/products/demo-chair",
                manufacturer=_manufacturer(complete=True),
                supplier=Organization(
                    name="CIR4FUN Demo Supplier",
                    gln="4012345000016",
                    role=OrganizationRole.SUPPLIER,
                ),
            ),
            documentation=Documentation(
                digitalInstructionsLink="https://example.invalid/docs/demo-chair",
                safetyInstructionsLink="https://example.invalid/docs/demo-chair-safety",
                downloadable=True,
                availableForYears=10,
                paperCopyAvailableOnRequest=True,
            ),
        ),
        classification=ProductClassification(
            sector="Furniture",
            group="Seating",
            category="Office Chair",
            subCategory="Ergonomic Office Chair",
            tags=("ergonomic", "adjustable"),
        ),
        characteristics=Characteristics(
            productName="CIR4FUN Demo Chair",
            description="Deterministic complete SDK demonstration fixture",
            brand="CIR4FUN",
            productType="Office Chair",
            dimensions=Dimensions(width=60.0, height=120.0, depth=60.0, unit="cm"),
            weight=14.5,
            color="blue",
            features=("lumbar-support", "height-adjustable"),
        ),
        billOfMaterials=BillOfMaterials(
            materials=(
                Material(name="Steel", mandatory=True, portion=0.6, reference="MAT-STEEL"),
                Material(name="Foam", portion=0.4, reference="MAT-FOAM"),
            ),
            components=(Component(name="Seat assembly", reference="COMP-SEAT"),),
            parts=(Part(name="Fastener set", mandatory=True, reference="PART-FASTENER"),),
        ),
    )
