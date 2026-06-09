"""Furniture-specific DPP aggregate, validation, and JSON transport.

Port of `dppsdk.dpp4fun.*` from ../dpp-sdk-platform/dpp-datamodel/dpp4fun.
"""

from .model import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Material,
    Part,
    ProductClassification,
)
from .transport import Dpp4FunJsonCodec, from_json, from_json_and_validate, to_json
from .validation import validate_dpp4fun

__all__ = [
    "BillOfMaterials",
    "Characteristics",
    "Component",
    "Dimensions",
    "Dpp4Fun",
    "Dpp4FunJsonCodec",
    "Material",
    "Part",
    "ProductClassification",
    "from_json",
    "from_json_and_validate",
    "to_json",
    "validate_dpp4fun",
]
