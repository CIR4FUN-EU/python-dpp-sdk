"""Pure policy used by the manual workflow after a pinned verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def classify_pinned_report(payload: Mapping[str, Any]) -> str:
    """Return COMPLETE, RUN_051, or PINNED_FAILED for retained JSON data."""

    results = payload.get("results")
    if not isinstance(results, Sequence):
        return "PINNED_FAILED"
    blocking = [
        result
        for result in results
        if isinstance(result, Mapping)
        and result.get("status") != "PASSED"
        and result.get("scenario_id") != "IMG-02"
    ]
    if blocking:
        return "PINNED_FAILED"
    if payload.get("image_equivalence") == "DIFFERENT_BUILD":
        return "RUN_051"
    img_02 = next(
        (
            result
            for result in results
            if isinstance(result, Mapping) and result.get("scenario_id") == "IMG-02"
        ),
        None,
    )
    return (
        "COMPLETE" if img_02 is not None and img_02.get("status") == "PASSED" else "PINNED_FAILED"
    )
