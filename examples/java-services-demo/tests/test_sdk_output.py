from __future__ import annotations

from dpp_java_services_demo.__main__ import _report
from dpp_java_services_demo.reporting import DemoReport, ScenarioResult, ScenarioStatus, render_text


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
    assert "SDK-07 | Valid immutable updates" in text
    assert "Purpose\n" not in text
    assert "expected_error=0" in text


def test_sdk_detailed_text_keeps_an_unexpected_failure_visible() -> None:
    base = _report("sdk")
    failure = ScenarioResult(
        scenario_id="SDK-01",
        name="Complete model construction",
        category="SDK_LOCAL",
        status=ScenarioStatus.FAILED,
        duration_seconds=0.0,
        summary="Scenario raised an unexpected exception",
        details="RuntimeError: controlled failure",
    )
    report = DemoReport(
        **{
            **base.__dict__,
            "results": (failure, *base.results[1:]),
            "mode_verdict": "SDK_DEMONSTRATION_FAILED",
        }
    )

    text = render_text(report)

    assert "[SDK-01] Complete model construction" in text
    assert "Status: FAILED" in text
    assert "RuntimeError: controlled failure" in text


def test_sdk_detailed_text_uses_a_stable_demonstration_identity() -> None:
    first = render_text(_report("sdk"))
    second = render_text(_report("sdk"))

    assert first == second
