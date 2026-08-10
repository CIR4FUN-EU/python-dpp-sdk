"""Maintainer CLI for exhaustive contract and release verification."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .reporting import has_required_failure, render_json, render_text
from .verification.runner import run_maintainer_mode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dpp_java_services_demo.maintainer")
    parser.add_argument("mode", choices=("sdk-contracts", "live", "verify"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--compose-project")
    parser.add_argument("--sdk-wheel", type=Path)
    parser.add_argument("--report-file", type=Path, help="Write retained JSON evidence atomically")
    parser.add_argument("--json", action="store_true")
    return parser


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
    print(render_json(report) if args.json else render_text(report))
    return 1 if has_required_failure(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
