"""Strict verification composition kept separate from the public demo CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..config import load_config
from ..reporting import DemoReport


def run_maintainer_mode(
    mode: Literal["sdk-contracts", "live", "verify"],
    *,
    env_file: Path | None = None,
    legacy: bool = False,
    compose_project: str | None = None,
    sdk_wheel: Path | None = None,
) -> DemoReport:
    """Run exhaustive SDK, live, or aggregate verification with existing report semantics."""
    # Import lazily so normal public SDK usage never imports maintainer-only tooling.
    from ..__main__ import _report

    if mode == "sdk-contracts":
        return _report("sdk", execution_profile="sdk-contracts")
    if mode == "live":
        return _report(
            "full",
            lambda: load_config(env_file, legacy=legacy),
            execution_profile="full",
        )
    return _report(
        "verify",
        lambda: load_config(env_file, legacy=legacy),
        execution_profile="verify",
        compose_project=compose_project,
        sdk_wheel=sdk_wheel,
    )
