"""Read-only conformance tests for Java Dpp4Fun fixtures.

The metadata was generated at Java commit
``9933d674ba27cd987f1bba731eb57b8dbb6bba95`` by
``DeterministicFixtureGenerator``.  Fixtures are test inputs only: production
transport never imports this directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dpp_sdk.core.errors import DppMappingError, DppValidationError
from dpp_sdk.dpp4fun.transport import from_json, from_json_and_validate, to_json

_FIXTURE_DIR = Path("docs/java-python-parity/java-source-of-truth/golden-fixtures")
_METADATA = json.loads((_FIXTURE_DIR / "fixture-metadata.json").read_text(encoding="utf-8"))
_CONTRACT_IDS = {
    "models:valid-complete-dpp": "FIXTURE-MODELS-VALID-COMPLETE-DPP",
    "models:valid-minimal-dpp": "FIXTURE-MODELS-VALID-MINIMAL-DPP",
    "models:valid-flat-input": "FIXTURE-MODELS-VALID-FLAT-INPUT",
    "models:valid-nested-input": "FIXTURE-MODELS-VALID-NESTED-INPUT",
    "models:canonical-java-output": "FIXTURE-MODELS-CANONICAL-JAVA-OUTPUT",
    "errors:malformed-json": "FIXTURE-ERRORS-MALFORMED-JSON",
    "errors:invalid-missing-required-field": "FIXTURE-ERRORS-INVALID-MISSING-REQUIRED-FIELD",
    "errors:invalid-semantic-rule": "FIXTURE-ERRORS-INVALID-SEMANTIC-RULE",
    "errors:invalid-cross-object-rule": "FIXTURE-ERRORS-INVALID-CROSS-OBJECT-RULE",
}


def _fixture_parameters() -> list[object]:
    fixtures = _METADATA["fixtures"]
    assert {entry["fixtureId"] for entry in fixtures} == set(_CONTRACT_IDS)
    return [
        pytest.param(_CONTRACT_IDS[entry["fixtureId"]], entry, id=_CONTRACT_IDS[entry["fixtureId"]])
        for entry in fixtures
    ]


@pytest.mark.parametrize(("contract_id", "entry"), _fixture_parameters())
def test_java_fixture_hash_and_contract_outcome(contract_id: str, entry: dict[str, object]) -> None:
    path = _FIXTURE_DIR / str(entry["file"])
    raw = path.read_text(encoding="utf-8")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]

    if entry["expectedOutcome"] == "success":
        parsed = from_json_and_validate(raw)
        if contract_id == "FIXTURE-MODELS-CANONICAL-JAVA-OUTPUT":
            # JSON object ordering is non-normative; list order remains normative.
            assert json.loads(to_json(parsed)) == json.loads(raw)
        else:
            assert from_json(to_json(parsed)) == parsed
        return

    if entry["expectedException"] == "MappingException":
        with pytest.raises(DppMappingError) as exc:
            from_json(raw)
        assert isinstance(exc.value.__cause__, ValidationError)
        return

    if entry["expectedException"] == "IllegalArgumentException":
        with pytest.raises(DppMappingError) as exc:
            from_json(raw)
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
        return

    assert entry["expectedException"] == "ValidationException"
    # Mapping succeeds; the explicit validated decoder retains the semantic category.
    from_json(raw)
    with pytest.raises(DppValidationError):
        from_json_and_validate(raw)
