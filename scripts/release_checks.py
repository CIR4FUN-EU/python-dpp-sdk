"""Small, dependency-free checks used by release tests and GitHub Actions."""

from __future__ import annotations

import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

_VERSION = re.compile(r"^v(\d+\.\d+\.\d+)$")
_ENVIRONMENT_PARTS = {".venv", "venv", "env", "site-packages", "dist-packages"}
_LOCAL_PARTS = {
    ".codex",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "scripts",
    "include",
    "lib",
    "bin",
}


def tag_matches_package_version(tag: str, package_version: str) -> bool:
    """Return whether the sole supported tag form exactly matches package version."""
    match = _VERSION.fullmatch(tag)
    return match is not None and bool(package_version) and match.group(1) == package_version


def is_forbidden_archive_member(member: str) -> bool:
    """Reject generated/local archive members using path components, not substrings."""
    parts = PurePosixPath(member).parts
    if not parts:
        return False
    relative_parts = parts[1:] if len(parts) > 1 and parts[0].startswith("dpp_sdk-") else parts
    lowered = tuple(part.lower() for part in relative_parts)
    if any(part in _ENVIRONMENT_PARTS or part.endswith("-venv") for part in lowered):
        return True
    if any(part in _LOCAL_PARTS for part in lowered):
        return True
    generated_reports = {
        "pyvenv.cfg",
        "verification-report.json",
        "legacy-verification-report.json",
    }
    if any(part in generated_reports for part in lowered):
        return True
    if any(part == "agents.md" for part in lowered):
        return True
    return "docs" in lowered and "python-agent-drafts" in lowered


def archive_forbidden_members(archive_path: str) -> list[str]:
    """Return forbidden source-distribution members for a release gate."""
    with tarfile.open(archive_path) as archive:
        return [
            member.name
            for member in archive.getmembers()
            if is_forbidden_archive_member(member.name)
        ]


def validate_release_workflow(workflow: str) -> list[str]:
    """Check the required release dependency and verification structure without PyYAML."""
    required = (
        "quality:",
        "needs: quality",
        "python -m pytest",
        "python -m pytest examples/mock-services-demo",
        "ruff check .",
        "ruff format --check .",
        "mypy",
        'tag-version "$GITHUB_REF_NAME"',
        "archive-members",
        "python -m twine check",
        "python -m pip check",
        "dpp_sdk.__version__",
        "release_checks.py package-version",
        "EXPECTED_PACKAGE_VERSION",
        "publish-testpypi:",
        "needs: build",
        "publish-pypi:",
        "needs: publish-testpypi",
    )
    errors = [marker for marker in required if marker not in workflow]
    if re.search(r"dpp_sdk\.__version__\s*==\s*['\"]", workflow):
        errors.append("dynamic installed package-version assertion")
    return errors


def _package_version() -> str:
    source = Path(__file__).parents[1] / "src" / "dpp_sdk" / "__init__.py"
    match = re.search(
        r'^__version__\s*=\s*"([^"]+)"', source.read_text(encoding="utf-8"), re.MULTILINE
    )
    if match is None:
        raise ValueError("package version is unavailable")
    return match.group(1)


def main(arguments: list[str]) -> int:
    if arguments == ["package-version"]:
        print(_package_version())
        return 0
    if arguments[:1] == ["tag-version"] and len(arguments) == 2:
        return 0 if tag_matches_package_version(arguments[1], _package_version()) else 1
    if arguments[:1] == ["archive-members"] and len(arguments) == 2:
        forbidden = archive_forbidden_members(arguments[1])
        if forbidden:
            print("forbidden archive members:", *forbidden, sep="\n")
            return 1
        return 0
    print(
        "usage: release_checks.py package-version | tag-version <tag> | archive-members <sdist>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
