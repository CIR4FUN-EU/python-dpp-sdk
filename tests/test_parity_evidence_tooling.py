"""Regression coverage for literal contract-ID discovery in parity evidence."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


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


def test_current_state_validator_reports_generated_contract_totals() -> None:
    """Current closure evidence must be derived from the regenerated contract."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / ".codex/task-logs/python-gap-implementation/validate_parity_state.py"),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    totals = json.loads(result.stdout)
    assert totals == {
        "capabilities": 405,
        "verified": 403,
        "implementedNotFullyTested": 0,
        "notVerified": 0,
        "blockedExternal": 2,
        "totalNonClosedWork": 0,
    }


def test_current_closure_validator_only_allows_documented_external_rows() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / ".codex/task-logs/python-gap-implementation/validate_closure.py"),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["result"] == "PASS"
    assert set(report["externalLimitations"]) == {
        "VALIDATION-CORE-VALIDATION-UTILS--A517C1",
        "VALIDATION-CORE-VALIDATION-UTILS--E376BD",
    }
    assert report["unexpectedUnresolved"] == {}
