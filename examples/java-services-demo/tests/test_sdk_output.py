from __future__ import annotations

from dpp_java_services_demo.__main__ import _report
from dpp_java_services_demo.reporting import render_text


def test_sdk_text_is_a_detailed_mode_specific_walkthrough() -> None:
    report = _report("sdk")

    text = render_text(report)

    assert "DPP Python SDK demonstration" in text
    assert "Verdict: SDK_DEMONSTRATION_PASSED" in text
    assert "Purpose" in text
    assert "Input" in text
    assert "SDK operation" in text
    assert "Observed result" in text
    assert "Explanation" in text
    assert "Why this matters" in text
    assert "repository_image" not in text
    assert "PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE" not in text


def test_sdk_text_summary_is_compact_and_keeps_statuses() -> None:
    report = _report("sdk")

    text = render_text(report, summary=True)

    assert "SDK-01 | Complete model construction" in text
    assert "SDK-17 | Registry request construction" in text
    assert "Purpose\n" not in text
    assert "EXPECTED_ERROR" in text
