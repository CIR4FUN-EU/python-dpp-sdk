"""Deterministic typed DPP4Fun demo fixtures with run-scoped identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from dpp_sdk import Dpp4Fun, DppHeader, Granularity
from dpp_sdk.core import DataElementCollection, SingleValuedDataElement
from dpp_sdk.dpp4fun import (
    Accessory,
    BillOfMaterials,
    CarbonFootprint,
    CarbonFootprintCalculation,
    Certificate,
    ChairCharacteristics,
    DesignRecord,
    Dpp4FunQuantity,
    Durability,
    EnvironmentalImpact,
    HealthImpact,
    HealthIndicator,
    Instruction,
    LengthUnit,
    Material,
    Nameplate,
    PostSaleService,
    ProductRelationship,
    Recyclability,
    Refurbishment,
    Reliability,
    Remanufacturing,
    Repairability,
    RepairRecord,
    Reusability,
    RightOfEndUsers,
    Safety,
    StandardAssessment,
    Traceability,
    Upgradability,
    Usage,
    WasteManagement,
    profile_definition,
)


def _profile_collection(path: str, **values: object) -> DataElementCollection:
    """Create a profile-backed composite for a source family without a named Python type."""
    definition = profile_definition(path)
    children = tuple(
        SingleValuedDataElement(
            element_id=field.element_id,
            dictionary_reference=field.dictionary_reference,
            value_data_type=field.value_data_type,
            value=value,
        )
        for name, value in values.items()
        if (field := profile_definition(f"{path}.{name}")).object_type == "SingleValuedDataElement"
    )
    if len(children) != len(values):
        raise ValueError(f"{path} accepts only the supplied scalar profile fields")
    return DataElementCollection(
        element_id=definition.element_id,
        object_type="DataElementCollection",
        dictionary_reference=definition.dictionary_reference,
        elements=children,
    )


@dataclass(frozen=True)
class DemoIdentity:
    """Run-scoped identifiers used by SDK and live scenarios."""

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


def _header(identity: DemoIdentity) -> DppHeader:
    return DppHeader(
        digital_product_passport_id=str(identity.dpp_id),
        unique_product_identifier=identity.product_id,
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id=f"operator-{identity.run_id.hex}",
    )


def build_minimal_fixture(identity: DemoIdentity) -> Dpp4Fun:
    """Build the smallest current typed furniture passport for the demo."""

    return Dpp4Fun.create(
        _header(identity),
        Nameplate.create(manufacturerName="CIR4FUN Demo Manufacturer"),
        ChairCharacteristics.create(color="blue", surface="Smooth"),
    )


def build_complete_fixture(identity: DemoIdentity) -> Dpp4Fun:
    """Build all 19 general aspects plus typed repeated, multilingual, unit, and record data."""

    materials = (
        Material.create(name="Steel", portion=0.6, mandatory=True),
        Material.create(name="Foam", portion=0.4),
    )
    characteristic = ChairCharacteristics.create(
        color="blue",
        surface="Woven matte",
        seatingCapacity=1,
        swivel=True,
    ).with_quantity("height", Dpp4FunQuantity(value=0.82, unit=LengthUnit.METER))
    return Dpp4Fun.create(
        _header(identity),
        Nameplate.create(
            gtinCode=identity.product_id,
            manufacturerName="CIR4FUN Demo Manufacturer",
            manufacturerProductDesignation={
                "en-US": "Demo Office Chair",
                "de-DE": "Demo-Bürostuhl",
            },
        ),
        BillOfMaterials.create(materialSet=tuple(item.element for item in materials)),
        CarbonFootprint.create(
            carbonFootprintCalculationSet=(
                CarbonFootprintCalculation.create(co2eq=18.5, phase="cradle-to-gate").element,
            )
        ),
        Durability.create(
            cycleLife="10,000 cycles",
            standardSet=(
                StandardAssessment.create(
                    name="CIR4FUN durability assessment",
                    description="Repeat cycle assessment for the demo chair.",
                    complianceStatus="compliant",
                ).element,
            ),
        ),
        EnvironmentalImpact.create(
            indicatorSet=(
                _profile_collection(
                    "environmentalImpact.indicatorSet[*]",
                    name="Climate impact",
                    description="Demonstration environmental indicator.",
                    value="18.5",
                    unit="kg CO2e",
                ),
            )
        ),
        HealthImpact.create(
            indicatorSet=(
                HealthIndicator.create(
                    name="Indoor emissions",
                    description="Demonstration health indicator.",
                    value="low",
                    unit="mg/m3",
                ).element,
            )
        ),
        ProductRelationship.create(
            accessorySet=(
                Accessory.create(
                    name="Replacement cushion",
                    description="Optional replacement cushion.",
                    reference="https://example.test/accessories/cushion",
                ).element,
            )
        ),
        Recyclability.create(recycledContent=0.35, recyclable=True),
        Refurbishment.create(
            refurbishmentInstructionSet=(
                _profile_collection(
                    "refurbishment.refurbishmentInstructionSet[*]",
                    name="Refinish the frame",
                    description="Clean and refinish the chair frame.",
                    reference="https://example.test/instructions/refinish",
                ),
            )
        ),
        Reliability.create(
            certificateSet=(
                Certificate.create(
                    name="CIR4FUN reliability assessment",
                    description="Demonstration reliability evidence.",
                    reference="https://example.test/certificates/reliability",
                ).element,
            )
        ),
        Remanufacturing.create(
            assemblyInstructionSet=(
                _profile_collection(
                    "remanufacturing.assemblyInstructionSet[*]",
                    name="Reassemble the frame",
                    description="Reassemble the refurbished chair frame.",
                    targetAudience="professional",
                    reference="https://example.test/instructions/reassemble",
                ),
            )
        ),
        Repairability.create(
            sparePartsAvailable=True,
            repairRecordSet=(
                RepairRecord.create(
                    name="Demo repair record",
                    description="A completed example repair.",
                    operator=f"operator-{identity.run_id.hex}",
                    time="2026-01-01T00:00:00Z",
                ).element,
            ),
        ),
        Reusability.create(secondHand=True),
        RightOfEndUsers.create(
            postSaleServiceSet=(
                PostSaleService.create(
                    name="Product support",
                    description="Contact the operator for product support.",
                    reference="https://example.test/support",
                ).element,
            )
        ),
        Safety.create(ageRestriction="adult", professionalUseOnly=False),
        Traceability.create(
            currentPhase="final-assembly",
            designRecordSet=(
                DesignRecord.create(
                    name="Chair design record",
                    description="Approved chair design record.",
                    operator=f"operator-{identity.run_id.hex}",
                    time="2026-01-01T00:00:00Z",
                    status="approved",
                ).element,
            ),
        ),
        Upgradability.create(upgradeOptionsAvailable=True),
        Usage.create(
            operatingHours=2000,
            assemblyInstructionSet=(
                Instruction.create(
                    name="Assemble the chair",
                    description="Attach the seat and backrest to the frame.",
                    reference="https://example.test/instructions/assembly",
                ).element,
            ),
        ),
        WasteManagement.create(toxicityRisk=False),
        characteristic,
    )
