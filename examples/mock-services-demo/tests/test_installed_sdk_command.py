"""Regression coverage for the SDK-only installed-consumer command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = DEMO_ROOT.parents[1]
_SERVICE_ENVIRONMENT_KEYS = {
    "DPP_REPO_IMAGE",
    "DPP_REGISTRY_IMAGE",
    "DPP_REPO_BASE_URL",
    "DPP_REGISTRY_BASE_URL",
    "DPP_REPO_PORT",
    "DPP_REGISTRY_PORT",
    "DPP_REQUEST_TIMEOUT_SECONDS",
}
EXPECTED_SDK_IDS = (
    "SDK-01",
    "SDK-02",
    "SDK-03",
    "SDK-06",
    "SDK-07",
)


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_installed_sdk_command_needs_no_service_profile_or_checkout(tmp_path: Path) -> None:
    """The packaged SDK-only command must not find or load ``env/pinned.env``."""
    root_dist = tmp_path / "root-dist"
    demo_dist = tmp_path / "demo-dist"
    root_dist.mkdir()
    demo_dist.mkdir()

    assert (
        _run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(root_dist)],
            cwd=SDK_ROOT,
        ).returncode
        == 0
    )
    assert (
        _run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(demo_dist)],
            cwd=DEMO_ROOT,
        ).returncode
        == 0
    )

    installed_site = tmp_path / "installed-site"
    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()

    root_wheel = next(root_dist.glob("dpp_sdk-*.whl"))
    demo_wheel = next(demo_dist.glob("*.whl"))
    installation = _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(installed_site),
            "--no-deps",
            "--force-reinstall",
            str(root_wheel),
            str(demo_wheel),
        ],
        cwd=outside_checkout,
    )
    assert installation.returncode == 0, installation.stderr

    service_free_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in _SERVICE_ENVIRONMENT_KEYS and key != "PYTHONPATH"
    }
    service_free_environment["PYTHONPATH"] = str(installed_site)
    for command in (["sdk"], ["sdk", "--summary"], ["sdk", "--json"]):
        result = _run(
            [sys.executable, "-m", "dpp_mock_services_demo", *command],
            cwd=outside_checkout,
            env=service_free_environment,
        )

        assert result.returncode == 0, result.stderr
        if "--json" in command:
            report = json.loads(result.stdout)
            assert tuple(item["scenario_id"] for item in report["results"]) == EXPECTED_SDK_IDS
            assert [item["scenario_id"] for item in report["results"]] == sorted(
                item["scenario_id"] for item in report["results"]
            )
            assert report["scenario_totals"] == {
                "total": 5,
                "passed": 5,
                "expected_error": 0,
                "failed": 0,
                "skipped": 0,
                "not_implemented": 0,
            }
            assert Path(report["sdk_location"]).is_relative_to(installed_site)
            assert report["mode_verdict"] == "SDK_DEMONSTRATION_PASSED"
            assert report["teaching_schema_version"] == 1
            assert all(item["teaching"]["purpose"] for item in report["results"])
        elif "--summary" in command:
            assert "summary_totals: total=5 pass=5 expected_error=0 fail=0" in result.stdout
        else:
            assert "DPP Python SDK demonstration" in result.stdout
            assert "Purpose" in result.stdout
            assert "Observed result" in result.stdout

    isolated_environment = tmp_path / "isolated-environment"
    created_environment = _run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(isolated_environment)],
        cwd=outside_checkout,
    )
    assert created_environment.returncode == 0, created_environment.stderr
    python_relative_path = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    isolated_python = isolated_environment / python_relative_path
    isolated_install = _run(
        [
            str(isolated_python),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            str(root_wheel),
            str(demo_wheel),
        ],
        cwd=outside_checkout,
    )
    assert isolated_install.returncode == 0, isolated_install.stderr
    maintainer = _run(
        [
            str(isolated_python),
            "-I",
            "-m",
            "dpp_mock_services_demo.maintainer",
            "sdk-contracts",
            "--json",
        ],
        cwd=outside_checkout,
        env=service_free_environment,
    )
    assert maintainer.returncode == 0, maintainer.stderr
    maintainer_report = json.loads(maintainer.stdout)
    assert tuple(item["scenario_id"] for item in maintainer_report["results"]) == tuple(
        f"SDK-{index:02d}" for index in range(1, 18)
    )
    assert Path(maintainer_report["sdk_location"]).is_relative_to(isolated_environment)
