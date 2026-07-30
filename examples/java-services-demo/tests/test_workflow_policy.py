from __future__ import annotations

import pytest

from dpp_java_services_demo.workflow_policy import classify_pinned_report


@pytest.mark.parametrize(
    ("equivalence", "statuses", "expected"),
    [
        ("SAME_BUILD", ("PASSED", "PASSED"), "COMPLETE"),
        ("DIFFERENT_BUILD", ("PASSED", "FAILED"), "RUN_050"),
        ("DIFFERENT_BUILD", ("FAILED", "FAILED"), "PINNED_FAILED"),
    ],
)
def test_pinned_workflow_followup_policy(
    equivalence: str,
    statuses: tuple[str, str],
    expected: str,
) -> None:
    payload = {
        "image_equivalence": equivalence,
        "results": [
            {"scenario_id": "REP-01", "status": statuses[0]},
            {"scenario_id": "IMG-02", "status": statuses[1]},
        ],
    }

    assert classify_pinned_report(payload) == expected
