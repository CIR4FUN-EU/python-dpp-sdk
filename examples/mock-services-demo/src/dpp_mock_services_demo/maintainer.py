"""Maintainer CLI for exhaustive contract and release verification."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .reporting import DemoReport, has_required_failure, render_json, render_text, scenario_totals
from .verification.runner import run_maintainer_mode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dpp_mock_services_demo.maintainer")
    parser.add_argument("mode", choices=("sdk-contracts", "live", "verify"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--compose-project")
    parser.add_argument("--sdk-wheel", type=Path)
    parser.add_argument("--report-file", type=Path, help="Write retained JSON evidence atomically")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Emit one verification verdict line instead of scenario details",
    )
    return parser


def _summary_line(report: DemoReport) -> str:
    """Render a compact result for long-running verification commands."""
    totals = scenario_totals(report.results)
    mode = report.mode.replace("-", "_").upper()
    return (
        f"{mode}: verdict={report.verdict} total={totals.total} passed={totals.passed} "
        f"expected_error={totals.expected_error} failed={totals.failed} "
        f"skipped={totals.skipped} not_implemented={totals.not_implemented}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_maintainer_mode(
            args.mode,
            env_file=args.env_file,
            legacy=args.legacy,
            compose_project=args.compose_project,
            sdk_wheel=args.sdk_wheel,
        )
    except ValueError as exc:
        print(f"configuration error: {exc}")
        return 2
    if args.report_file is not None:
        from .__main__ import _write_report

        _write_report(args.report_file, report)
    print(
        render_json(report)
        if args.json
        else _summary_line(report)
        if args.summary
        else render_text(report)
    )
    return 1 if has_required_failure(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
