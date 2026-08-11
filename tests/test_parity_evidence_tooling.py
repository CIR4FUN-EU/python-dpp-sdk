"""Portable regression coverage for literal contract-ID discovery."""

from __future__ import annotations

import re


def test_generator_discovers_every_literal_contract_id() -> None:
    test_text = """
    pytest.param("VALIDATION-CORE-ADDRESS-ADDRESS-VALIDATOR-CCD6BD")
    pytest.param("ERROR-VALIDATION-001")
    pytest.param("CLIENT-REPO-CREATE-DPP-001")
    pytest.param("MODEL-CORE-ADDRESS")
    """
    discovered = set(re.findall(r'"([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)"', test_text))
    assert discovered == {
        "VALIDATION-CORE-ADDRESS-ADDRESS-VALIDATOR-CCD6BD",
        "ERROR-VALIDATION-001",
        "CLIENT-REPO-CREATE-DPP-001",
        "MODEL-CORE-ADDRESS",
    }
