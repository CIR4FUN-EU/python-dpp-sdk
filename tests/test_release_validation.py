"""Regression tests for release artifacts and publication workflow gates."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_CHECKS = ROOT / "scripts" / "release_checks.py"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _release_checks():
    spec = importlib.util.spec_from_file_location("release_checks", RELEASE_CHECKS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _current_package_version() -> str:
    return _release_checks()._package_version()


def test_archive_member_policy_rejects_local_environment_and_internal_paths() -> None:
    checks = _release_checks()
    forbidden = (
        ".java-services-demo-venv/Lib/site-packages/httpx/__init__.py",
        ".venv/bin/python",
        "nested/env/lib/python3.12/site-packages/pydantic/__init__.py",
        "nested/dist-packages/httpx/__init__.py",
        "pyvenv.cfg",
        "nested/pyvenv.cfg",
        ".codex/task-logs/run.md",
        "AGENTS.md",
        "docs/python-agent-drafts/notes.md",
        "examples/java-services-demo/verification-report.json",
        "build/output.whl",
        "dist/output.whl",
    )
    for member in forbidden:
        assert checks.is_forbidden_archive_member(member), member

    allowed = (
        f"dpp_sdk-{_current_package_version()}/README.md",
        f"dpp_sdk-{_current_package_version()}/LICENSE",
        f"dpp_sdk-{_current_package_version()}/src/dpp_sdk/py.typed",
        f"dpp_sdk-{_current_package_version()}/tests/test_clients.py",
    )
    for member in allowed:
        assert not checks.is_forbidden_archive_member(member), member


def test_root_sdist_excludes_local_environment_and_generated_output(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    archive = next(output.glob("dpp_sdk-*.tar.gz"))
    checks = _release_checks()
    with tarfile.open(archive) as source_distribution:
        forbidden = [
            member.name
            for member in source_distribution.getmembers()
            if checks.is_forbidden_archive_member(member.name)
        ]
    assert forbidden == []


def _build_sdist(checkout: Path, output: Path) -> Path:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(output)],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return next(output.glob("dpp_sdk-*.tar.gz"))


def _archive_member_names(archive: Path) -> list[str]:
    with tarfile.open(archive) as source_distribution:
        return [member.name for member in source_distribution.getmembers()]


def test_root_sdist_excludes_fake_environment_from_copied_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    shutil.copytree(
        ROOT,
        checkout,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    environment = checkout / "src" / "dpp_sdk" / "archive-test-venv"
    metadata = environment / "Lib" / "site-packages" / "foreign_package-1.0.dist-info" / "METADATA"
    metadata.parent.mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("home = fake\n", encoding="utf-8")
    (environment / "bin").mkdir()
    (environment / "bin" / "python").write_text("fake executable\n", encoding="utf-8")
    metadata.write_text("Name: foreign-package\n", encoding="utf-8")
    (environment / "leak-marker.txt").write_text("must not be packaged\n", encoding="utf-8")

    checks = _release_checks()
    clean_members = _archive_member_names(_build_sdist(checkout, tmp_path / "clean"))
    assert not any(checks.is_forbidden_archive_member(member) for member in clean_members)

    pyproject = checkout / "pyproject.toml"
    compromised = pyproject.read_text(encoding="utf-8").replace('    "**/*-venv/**",\n', "")
    pyproject.write_text(compromised, encoding="utf-8")
    compromised_members = _archive_member_names(_build_sdist(checkout, tmp_path / "compromised"))
    leaked_members = [member for member in compromised_members if "archive-test-venv" in member]
    assert set(leaked_members) == {
        f"dpp_sdk-{_current_package_version()}/src/dpp_sdk/archive-test-venv/bin/python",
        f"dpp_sdk-{_current_package_version()}/src/dpp_sdk/archive-test-venv/leak-marker.txt",
    }
    assert all(checks.is_forbidden_archive_member(member) for member in leaked_members)


@pytest.mark.parametrize(
    ("tag", "package_version", "expected"),
    (
        ("v0.2.1", "0.2.1", True),
        ("v0.2.2", "0.2.1", False),
        ("v1.2.1", "0.2.1", False),
        ("v0.2.1-rc1", "0.2.1", False),
        ("release-0.2.1", "0.2.1", False),
        ("", "0.2.1", False),
        ("v0.2.1", "", False),
    ),
)
def test_tag_version_match_is_exact(tag: str, package_version: str, expected: bool) -> None:
    assert _release_checks().tag_matches_package_version(tag, package_version) is expected


def test_tag_version_cli_accepts_only_the_current_exact_tag() -> None:
    checks = _release_checks()
    package_version = _current_package_version()
    assert checks.main(["tag-version", f"v{package_version}"]) == 0
    assert checks.main(["tag-version", "v999.999.999"]) == 1


def test_package_version_cli_reports_the_current_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    checks = _release_checks()
    assert checks.main(["package-version"]) == 0
    assert capsys.readouterr().out.strip() == _current_package_version()


def test_release_workflow_requires_all_quality_gates_before_publish() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    checks = _release_checks()
    errors = checks.validate_release_workflow(workflow)
    assert errors == []


def test_release_workflow_uses_dynamic_package_version_for_installed_import_proof() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "release_checks.py package-version" in workflow
    assert "EXPECTED_PACKAGE_VERSION" in workflow
    assert 'dpp_sdk.__version__ == "0.2.1"' not in workflow


def test_release_workflow_validator_rejects_literal_installed_version_assertion() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    literal_workflow = workflow.replace(
        'dpp_sdk.__version__ == os.environ["EXPECTED_PACKAGE_VERSION"]',
        'dpp_sdk.__version__ == "0.2.1"',
    )
    assert (
        "dynamic installed package-version assertion"
        in _release_checks().validate_release_workflow(literal_workflow)
    )
