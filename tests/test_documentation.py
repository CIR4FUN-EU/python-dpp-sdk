"""Deterministic checks for maintained consumer documentation."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = (
    "README.md",
    "RELEASING.md",
    "CONTRIBUTING.md",
    "docs/model-guide.md",
    "docs/clients-guide.md",
    "docs/extending.md",
    "docs/conformance.md",
    "docs/dpp4fun-fields.md",
    "src/dpp_sdk/core/README.md",
    "src/dpp_sdk/dpp4fun/README.md",
    "src/dpp_sdk/clients/README.md",
    "examples/mock-services-demo/README.md",
    "examples/mock-services-demo/ADVANCED_OPERATIONS.md",
)
FAMILIES = {
    "README.md": (
        "## Install",
        "## Create, save, and register a passport",
        "## How the SDK is organized",
        "## Handle errors",
        "## Documentation",
        "## Standards and limitations",
        "## Versioning",
    ),
    "docs/model-guide.md": (
        "## Overview",
        "## Build a core passport",
        "## Build a DPP4Fun passport",
        "## Read fields",
        "## Edit",
        "## Validate",
        "## Convert to and from JSON",
    ),
    "docs/conformance.md": (
        "## Source alignment and source conflicts",
        "## Core rules",
        "## DPP4Fun rules",
    ),
    "docs/clients-guide.md": (
        "## Public operations",
        "## Envelopes and errors",
        "## Pagination and registry metadata",
        "## Decode a response into a typed passport",
    ),
    "CONTRIBUTING.md": (
        "## Set up the development environment",
        "## Checks",
        "## Architecture diagrams",
        "## Mock-service verification",
    ),
}
EXECUTED_GUIDES = ("docs/model-guide.md", "docs/extending.md")
REPOSITORY_OPERATIONS = (
    "create_dpp",
    "read_dpp_by_id",
    "read_dpp_by_product_id",
    "read_dpp_version_by_id_and_date",
    "read_dpp_ids_by_product_ids",
    "update_dpp_by_id",
    "read_data_element",
    "update_data_element",
    "delete_dpp_by_id",
)
DIAGRAM_STEMS = (
    "python-sdk-overview",
    "python-client-request-flow",
    "python-core-model",
    "python-dpp4fun-model",
)
COMMAND_DOCUMENTS = (
    "CONTRIBUTING.md",
    "RELEASING.md",
    "examples/mock-services-demo/README.md",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_mock_services_demo_replaces_the_legacy_identity() -> None:
    """The optional demo must not retain its former identity."""
    legacy_demo_name = "j" + "ava-services-demo"
    assert (ROOT / "examples" / "mock-services-demo").is_dir()
    assert not (ROOT / "examples" / legacy_demo_name).exists()


def test_maintained_documentation_does_not_require_the_parent_workspace_layout() -> None:
    workspace_path = "Dpp-SDK-python/dpp-python-sdk"

    for relative in MARKDOWN_FILES:
        assert workspace_path not in _read(relative), relative


def _anchor(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", value.strip().lower().replace(" ", "-"))


def _headings(text: str) -> set[str]:
    return {_anchor(item) for item in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)}


def _case_exact_path(source: Path, target: str) -> Path:
    current = source.parent
    for part in PurePosixPath(target).parts:
        if part == ".":
            continue
        if part == "..":
            current = current.parent
            continue
        matches = [child for child in current.iterdir() if child.name == part]
        assert matches, f"missing or case-mismatched path: {source.relative_to(ROOT)} -> {target}"
        current = matches[0]
    return current


def _validate_links(relative: str, text: str) -> None:
    source = ROOT / relative
    for target, anchor in re.findall(r"(?<!!)\[[^\]]+\]\(([^)#]+)(?:#([^)]+))?\)", text):
        if "://" in target or target.startswith("mailto:"):
            continue
        resolved = _case_exact_path(source, target)
        assert resolved.is_file(), f"link is not a file: {relative} -> {target}"
        if anchor:
            assert _anchor(anchor) in _headings(resolved.read_text(encoding="utf-8"))
    for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        assert "\\" not in target, f"Windows separator in image path: {relative} -> {target}"
        assert _case_exact_path(source, target).suffix.lower() in {".svg", ".png"}


def _fences(text: str, language: str) -> list[str]:
    return re.findall(rf"(?ms)^(?:[~]|\x60){{3}}{language}\s*\n(.*?)(?:[~]|\x60){{3}}\s*$", text)


def _operation_section(text: str, operation: str, occurrence: int = 0) -> str:
    sections = re.findall(rf"(?ms)^### {re.escape(operation)}\s*$\n(.*?)(?=^### |\Z)", text)
    assert len(sections) > occurrence, f"missing operation section: {operation}"
    return sections[occurrence]


def _validate_operation_section(section: str, operation: str) -> None:
    lowered = section.lower()
    for marker in (
        "purpose:",
        "signature:",
        "http:",
        "body",
        "response",
        "null",
        "limit:",
        "evidence:",
    ):
        assert marker in lowered, f"{operation} missing {marker}"


def _validate_client_operations(text: str) -> None:
    for operation in REPOSITORY_OPERATIONS:
        assert f"`{operation}" in text or f"| `{operation}" in text, operation
    assert "post_new_dpp_to_registry" in text
    for obsolete in (
        "health_check",
        "read_compressed_dpp_by_id",
        "read_dpp_version_by_product_id_and_date",
        "DppCodec",
        "UpdateDataElementRequest",
        "deprecated unversioned compatibility route",
    ):
        assert obsolete not in text


def _validate_diagram_pairs(directory: Path) -> None:
    for stem in DIAGRAM_STEMS:
        assert (directory / f"{stem}.mmd").is_file()
        assert (directory / f"{stem}.svg").is_file()


def _validate_python_blocks(text: str) -> None:
    for block in _fences(text, "python"):
        tree = ast.parse(block)
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                module = node.names[0].name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.split(".")[0]
            if module:
                assert importlib.util.find_spec(module) is not None, module


def _validate_root_command_convention(overrides: dict[str, str] | None = None) -> None:
    overrides = overrides or {}
    for relative in COMMAND_DOCUMENTS:
        text = overrides.get(relative, _read(relative))
        assert re.search(r"Run from:.*?root", text, re.DOTALL), (
            f"{relative} does not state repository root as its command working directory"
        )
    demo = overrides.get(
        "examples/mock-services-demo/README.md", _read("examples/mock-services-demo/README.md")
    )
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")
    assert "from `examples/mock-services-demo`" not in demo + operations
    assert "docker compose --env-file $envFile -f $composeFile -p $project up -d --wait" in demo
    assert "[ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md)" in demo


def test_documentation_structure_links_examples_payloads_and_diagrams() -> None:
    for relative in MARKDOWN_FILES:
        text = _read(relative)
        assert not re.search(r"[A-Za-z]:\\\\", text), f"absolute Windows path in {relative}"
        _validate_links(relative, text)
        for block in _fences(text, "json"):
            json.loads(block)
        _validate_python_blocks(text)
    for relative, headings in FAMILIES.items():
        text = _read(relative)
        for heading in headings:
            assert heading in text, f"{relative} missing {heading}"
    _validate_client_operations(_read("docs/clients-guide.md"))
    _validate_diagram_pairs(ROOT / "docs/architecture")
    _validate_root_command_convention()


def test_package_manifest_includes_maintained_diagram_sources_and_previews() -> None:
    import tomllib

    manifest = tomllib.loads(_read("pyproject.toml"))
    included = manifest["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]

    assert "docs/architecture/*.mmd" in included
    assert "docs/architecture/*.svg" in included
    _validate_diagram_pairs(ROOT / "docs" / "architecture")


def test_client_guide_example_uses_the_flat_canonical_passport_shape() -> None:
    guide = _read("docs/clients-guide.md")
    assert '"digitalProductPassportId"' in guide
    assert '"elements"' in guide
    assert '"dpp_header"' not in guide


def test_demo_readme_leads_with_small_consumer_sdk_use() -> None:
    demo = _read("examples/mock-services-demo/README.md")

    assert "-m dpp_mock_services_demo sdk" in demo
    assert demo.index("## Quick start") < demo.index("## Optional connected demo")


def test_root_readme_renders_on_pypi_and_starts_services_without_a_checkout() -> None:
    readme = _read("README.md")

    # PyPI cannot resolve repository-relative paths, so every link and image must be absolute.
    for target in re.findall(r"\]\(([^)]+)\)", readme) + re.findall(r'src="([^"]+)"', readme):
        assert "://" in target, f"relative link breaks on PyPI: {target}"
    raw = "https://raw.githubusercontent.com/CIR4FUN-EU/python-dpp-sdk/main/"
    assert f"{raw}examples/mock-services-demo/compose.yaml" in readme
    assert (ROOT / "examples/mock-services-demo/compose.yaml").is_file()
    assert "pip install dpp-sdk" in readme
    assert "docker compose up -d --wait" in readme
    assert "docker compose down" in readme
    assert "--env-file" not in readme


def test_demo_guide_offers_native_compose_commands() -> None:
    demo = _read("examples/mock-services-demo/README.md")

    assert "docker compose --env-file $envFile -f $composeFile -p $project pull" in demo
    assert "docker compose --env-file $envFile -f $composeFile -p $project up -d --wait" in demo
    assert "[ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md)" in demo


def test_demo_setup_defines_compose_variables_used_by_operations_reference() -> None:
    demo = _read("examples/mock-services-demo/README.md")
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")
    environment = _read("examples/mock-services-demo/.env.example")

    assert '$composeFile = Join-Path $demoDir "compose.yaml"' in demo
    # The operations page defines its own variables before the first command that uses them.
    setup = operations.index("## Set up the variables first")
    assert operations.index('$composeFile = Join-Path $demoDir "compose.yaml"') > setup
    assert operations.index('compose_file="$demo_dir/compose.yaml"') > setup
    assert operations.index("$composeFile", setup) < operations.index("## Alternate ports")
    assert "does not guarantee that its images are publicly pullable" in operations
    assert "DPP_REPO_IMAGE=ghcr.io/cir4fun-eu/dpp-repo-api:" in environment
    assert "DPP_REGISTRY_IMAGE=ghcr.io/cir4fun-eu/dpp-registry-api:" in environment


def test_documentation_corruption_checks_fail_on_temporary_inputs(tmp_path: Path) -> None:
    temporary = tmp_path / "guide.md"
    temporary.write_text("## Purpose and scope\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        for heading in FAMILIES["docs/model-guide.md"]:
            assert heading in temporary.read_text(encoding="utf-8")

    client = _read("docs/clients-guide.md")
    with pytest.raises(AssertionError):
        _validate_client_operations(client.replace("read_dpp_by_id", "removed_operation"))
    with pytest.raises(json.JSONDecodeError):
        json.loads("{")
    with pytest.raises(AssertionError):
        _validate_python_blocks("~~~python\nfrom definitely_missing_sdk import value\n~~~")
    with pytest.raises(AssertionError):
        _case_exact_path(ROOT / "README.md", "docs/architecture/Python-sdk-overview.svg")
    with pytest.raises(AssertionError):
        _validate_diagram_pairs(tmp_path)
    with pytest.raises(AssertionError):
        assert not re.search(r"[A-Za-z]:\\\\", "C:\\\\absolute\\\\path")
    with pytest.raises(AssertionError):
        _validate_root_command_convention(
            {"CONTRIBUTING.md": _read("CONTRIBUTING.md").replace("Run from:", "")}
        )


def test_installation_and_demo_commands_keep_their_working_directory_contracts() -> None:
    contributing = _read("CONTRIBUTING.md")
    release = _read("RELEASING.md")
    demo = _read("examples/mock-services-demo/README.md")
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")

    assert "folder that contains `pyproject.toml`" in contributing
    assert "**Run from:** the repository root" in contributing
    assert "**Run from:** the Python repository root" in release
    assert "git pull https://github.com/CIR4FUN-EU/python-dpp-sdk.git main" in release
    assert "git push https://github.com/CIR4FUN-EU/python-dpp-sdk.git vX.Y.Z" in release
    assert "from `examples/mock-services-demo`" not in demo + operations
    assert '$project = "dpp-mock-services-demo-local"' in demo
    assert 'DPP_REPO_BASE_URL = "http://localhost:28080"' in operations
    assert "DPP_REPO_BASE_URL=http://localhost:28080" in operations
    assert "18080" in demo and "8080 and 8081" in demo
    assert "down" in demo
    assert "project-scoped" in demo


def test_command_guides_use_existing_relative_paths_and_separate_shells() -> None:
    readme = _read("README.md")
    release = _read("RELEASING.md")
    demo = _read("examples/mock-services-demo/README.md")
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")

    for relative in (
        "examples/mock-services-demo/compose.yaml",
        "examples/mock-services-demo/env/pinned.env",
        "examples/mock-services-demo/tests",
    ):
        assert (ROOT / relative).exists(), relative
    assert "~~~powershell" not in demo
    assert "```powershell" in readme
    assert "```bash" in readme
    assert "```powershell" in release
    assert "```powershell" in demo
    assert 'python -m build --outdir "$build_root"' in release
    assert "python -m twine check" in release
    assert "docker compose --env-file $envFile" in demo
    assert not re.search(r"[A-Za-z]:\\\\", readme + release + demo + operations)


def test_maintained_sdk_only_references_match_the_current_scenario_contract() -> None:
    demo = _read("examples/mock-services-demo/README.md")
    changelog = _read("CHANGELOG.md")
    scenario_path = ROOT / "examples/mock-services-demo" / "src/dpp_mock_services_demo"
    scenarios = (scenario_path / "sdk_scenarios.py").read_text(encoding="utf-8")

    assert "SDK-01 through SDK-17" in changelog
    assert '"SDK-12"' in scenarios
    assert '"SDK-13"' not in scenarios
    assert "[sdk_scenarios.py](src/dpp_mock_services_demo/sdk_scenarios.py)" in demo


def test_demo_report_commands_use_temporary_output_instead_of_the_worktree() -> None:
    demo = _read("examples/mock-services-demo/README.md")
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "examples/mock-services-demo/verification-report.json" not in demo + operations
    assert "verification-report.json" in ignored


def test_demo_readme_keeps_cleanup_with_the_live_lifecycle_and_links_operations() -> None:
    demo = _read("examples/mock-services-demo/README.md")

    assert "## Optional connected demo" in demo
    assert "[ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md)" in demo
    assert "manage-mock-services.ps1" in _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")
    assert "down" in demo


def test_full_demo_verification_uses_clean_wheels_and_runs_live_contracts_once() -> None:
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")

    assert "-m pytest .\\tests --run-mock-services --force-sugar" in operations
    assert "-m pytest -c .\\examples\\mock-services-demo\\pyproject.toml" in operations
    assert '$verifyVenv = Join-Path (Resolve-Path .).Path ".verify-venv"' in operations
    assert "dpp_mock_services_demo.maintainer verify" in operations
    assert "--summary" in operations
    assert "## Choose a verification level" in operations
    assert "19 live scenarios once" in operations


def test_demo_guides_keep_detailed_verification_outside_the_root_readme() -> None:
    demo = _read("examples/mock-services-demo/README.md")
    operations = _read("examples/mock-services-demo/ADVANCED_OPERATIONS.md")

    assert "Optional maintainer verification" in operations
    assert "dpp_mock_services_demo.maintainer" in operations
    for text in (demo, operations):
        assert "demo" in text
    assert "verify" in operations


def test_demo_readme_uses_a_short_consumer_path() -> None:
    demo = _read("examples/mock-services-demo/README.md")

    assert "## Quick start" in demo
    assert "## Optional connected demo" in demo
    assert "### PowerShell" in demo
    assert "### Bash (Linux/macOS)" in demo
    assert 'demo_dir="$(cd ./examples/mock-services-demo && pwd)"' in demo
    assert "python -m dpp_mock_services_demo sdk" in demo
    assert 'docker compose --env-file "$env_file"' in demo
    assert "## Optional maintainer verification" in _read(
        "examples/mock-services-demo/ADVANCED_OPERATIONS.md"
    )
    assert "[sdk_scenarios.py](src/dpp_mock_services_demo/sdk_scenarios.py)" in demo
    assert "[integration_scenarios.py](src/dpp_mock_services_demo/integration_scenarios.py)" in demo


def test_demo_readme_identifies_the_optional_wrapper_boundary() -> None:
    demo = _read("examples/mock-services-demo/README.md")

    assert "manage-mock-services.ps1" not in demo
    assert "Optional PowerShell lifecycle helper" in _read(
        "examples/mock-services-demo/ADVANCED_OPERATIONS.md"
    )
    assert "[ADVANCED_OPERATIONS.md](ADVANCED_OPERATIONS.md)" in demo


def test_demo_consumer_headings_remain_linkable() -> None:
    demo = _read("examples/mock-services-demo/README.md")
    headings = re.findall(r"^(#{1,6})\s+(.+)$", demo, re.MULTILINE)
    anchors = set()
    for _, title in headings:
        cleaned_title = re.sub(r"[^a-z0-9 -]", "", title.lower())
        anchors.add("#" + cleaned_title.replace(" ", "-"))
    assert {
        "#quick-start",
        "#optional-connected-demo",
    } <= anchors


def test_consumer_documentation_does_not_repeat_version_numbers() -> None:
    """Versions live in the bump checklist files only; docs must not need edits on a bump."""
    package = (ROOT / "src/dpp_sdk/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', package)
    assert match
    for relative in MARKDOWN_FILES:
        if relative in {"RELEASING.md", "CONTRIBUTING.md"}:  # name versioned service profiles
            continue
        text = _read(relative)
        assert match.group(1) not in text, f"{relative} repeats the package version"
        assert not re.search(r"ghcr\.io/\S+:\d", text), f"{relative} repeats an image tag"


@pytest.mark.parametrize("relative", EXECUTED_GUIDES)
def test_guide_code_blocks_run_in_order(relative: str) -> None:
    namespace: dict[str, object] = {"__name__": "guide"}
    for index, block in enumerate(_fences(_read(relative), "python")):
        exec(compile(block, f"{relative}[{index}]", "exec"), namespace)


def test_dpp4fun_field_reference_matches_the_bundled_profile() -> None:
    script = ROOT / "scripts" / "generate_dpp4fun_fields.py"
    spec = importlib.util.spec_from_file_location("generate_dpp4fun_fields", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _read("docs/dpp4fun-fields.md") == module.render(), (
        "docs/dpp4fun-fields.md is stale; run python scripts/generate_dpp4fun_fields.py"
    )
