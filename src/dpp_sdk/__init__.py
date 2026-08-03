"""Python SDK for Digital Product Passports (DPP).

Idiomatic Pydantic v2 implementation of the DPP SDK contracts.

Sub-packages:
    dpp_sdk.core      -- reusable core DPP model, validation, identifiers
    dpp_sdk.dpp4fun   -- furniture-specific DPP aggregate, validation, JSON transport
    dpp_sdk.clients   -- HTTP clients for the DPP repository and registry APIs
"""

from .core import (
    Address,
    Contact,
    Documentation,
    Dpp,
    DppCore,
    DppError,
    DppMappingError,
    DppValidationError,
    Email,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    Telephone,
    validate_dpp_core,
)
from .dpp4fun import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Dpp4FunJsonCodec,
    Material,
    Part,
    ProductClassification,
    from_json,
    from_json_and_validate,
    to_json,
    validate_dpp4fun,
)

__version__ = "0.2.1"

__all__ = [
    "Address",
    "BillOfMaterials",
    "Characteristics",
    "Component",
    "Contact",
    "Dimensions",
    "Documentation",
    "Dpp",
    "Dpp4Fun",
    "Dpp4FunJsonCodec",
    "DppCore",
    "DppError",
    "DppMappingError",
    "DppValidationError",
    "Email",
    "Material",
    "Nameplate",
    "Organization",
    "OrganizationRole",
    "PassportMetadata",
    "Part",
    "ProductClassification",
    "Telephone",
    "__version__",
    "from_json",
    "from_json_and_validate",
    "to_json",
    "validate_dpp4fun",
    "validate_dpp_core",
]
