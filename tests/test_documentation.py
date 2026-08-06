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
    "docs/overview.md",
    "docs/usage.md",
    "docs/model-guide.md",
    "docs/validation-guide.md",
    "docs/validation-rules.md",
    "docs/diagram-evidence.md",
    "src/dpp_sdk/core/README.md",
    "src/dpp_sdk/dpp4fun/README.md",
    "src/dpp_sdk/clients/README.md",
    "examples/java-services-demo/README.md",
    "examples/java-services-demo/OPERATIONS.md",
)
FAMILIES = {
    "README.md": (
        "## Start here",
        "## Architecture at a glance",
        "## Prerequisites",
        "## Install",
        "## Documentation and next steps",
    ),
    "docs/overview.md": (
        "## Purpose and scope",
        "## Architecture and package boundaries",
        "## Supported concepts",
        "## Intentional exclusions and limitations",
        "## Reading order and next steps",
    ),
    "docs/usage.md": ("## Purpose and scope", "## Installation", "## Errors", "Next:"),
    "docs/model-guide.md": (
        "## Purpose and scope",
        "## Reusable core",
        "## DPP4Fun models",
        "## Immutable updates and validation boundary",
        "## Limitations and next steps",
    ),
    "docs/validation-guide.md": (
        "## Purpose and scope",
        "## Construction versus semantic validation",
        "## Codec input, output, and failures",
        "## Errors, limitations, and next steps",
    ),
    "docs/validation-rules.md": (
        "## Purpose and scope",
        "## Core rules",
        "## DPP4Fun rules",
        "## Codec boundary, limitations, and next steps",
    ),
    "src/dpp_sdk/clients/README.md": (
        "## Purpose and scope",
        "## Shared response envelope, DTOs, and errors",
        "## Repository operation reference",
        "## Registry operation reference",
        "## Related documents and next steps",
    ),
}
REPOSITORY_OPERATIONS = (
    "health_check",
    "create_dpp",
    "read_dpp_by_id",
    "read_dpp_by_product_id",
    "read_compressed_dpp_by_id",
    "read_dpp_version_by_id_and_date",
    "read_dpp_version_by_product_id_and_date",
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
    "README.md",
    "RELEASING.md",
    "docs/usage.md",
    "docs/diagram-evidence.md",
    "src/dpp_sdk/core/README.md",
    "src/dpp_sdk/dpp4fun/README.md",
    "src/dpp_sdk/clients/README.md",
    "examples/java-services-demo/README.md",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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
        _validate_operation_section(_operation_section(text, operation), operation)
    _validate_operation_section(
        _operation_section(text, "health_check", 1), "registry health_check"
    )
    _validate_operation_section(
        _operation_section(text, "post_new_dpp_to_registry"), "post_new_dpp_to_registry"
    )
    assert text.count("### health_check") == 2
    assert "deprecated unversioned compatibility route" in text


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
        "examples/java-services-demo/README.md", _read("examples/java-services-demo/README.md")
    )
    operations = _read("examples/java-services-demo/OPERATIONS.md")
    assert "from `examples/java-services-demo`" not in demo + operations
    assert "manage-java-services.ps1" in demo
    assert "-Action Start" in demo
    assert 'pwsh -File "$service_script" -Action Start' in demo


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
    _validate_client_operations(_read("src/dpp_sdk/clients/README.md"))
    _validate_diagram_pairs(ROOT / "docs/architecture")
    _validate_root_command_convention()


def test_demo_readme_makes_sdk_json_output_easy_to_inspect() -> None:
    demo = _read("examples/java-services-demo/README.md")

    assert "sdk --json --report-file $sdkReport" in demo
    assert "Get-Content $sdkReport -TotalCount 24" in demo


def test_root_readme_quick_service_commands_use_one_env_file() -> None:
    readme = _read("README.md")

    assert "## Quick Java-service checks" in readme
    assert 'Copy-Item (Join-Path $demoDir ".env.example") $envFile' in readme
    assert "ConvertFrom-StringData" in readme
    assert 'Write-Host "Using Compose project: $project"' in readme
    assert "-Action Start -EnvFile $envFile" in readme
    assert 'pytest .\\tests -m "not integration"' in readme
    assert "tests\\test_integration_live.py --run-java-services" in readme
    assert "examples\\java-services-demo\\tests --run-java-services" in readme
    assert "successful Start command" in readme
    assert "## Linux/macOS quick checks" in readme
    assert 'cp "$demo_dir/.env.example" "$env_file"' in readme
    assert "printf 'Using Compose project: %s\\n' \"$project\"" in readme
    linux_start = 'pwsh -File "$demo_dir/manage-java-services.ps1"'
    linux_start += ' -Action Start -EnvFile "$env_file"'
    assert linux_start in readme
    assert 'pytest ./tests -m "not integration"' in readme
    assert "./tests/test_integration_live.py --run-java-services" in readme


def test_root_readme_live_checks_use_configured_endpoints() -> None:
    readme = _read("README.md")

    assert "$env:DPP_REPO_BASE_URL = $demoConfig.DPP_REPO_BASE_URL" in readme
    assert "$env:DPP_REGISTRY_BASE_URL = $demoConfig.DPP_REGISTRY_BASE_URL" in readme
    assert "export DPP_REPO_BASE_URL=\"$(sed -n 's/^DPP_REPO_BASE_URL=//p'" in readme
    assert "export DPP_REGISTRY_BASE_URL=\"$(sed -n 's/^DPP_REGISTRY_BASE_URL=//p'" in readme
    assert "published Java repository" in readme
    assert "registry images selected by `.env`" in readme
    assert "`http://localhost:18080/`" in readme
    assert "`http://localhost:18081/`" in readme
    assert "$demoDir = (Resolve-Path .\\java-services-demo).Path" in readme
    portable_start = 'pwsh -File (Join-Path $demoDir "manage-java-services.ps1")'
    portable_start += " -Action Start -EnvFile $envFile"
    assert portable_start in readme
    assert 'demo_dir="$(cd ./java-services-demo && pwd)"' in readme
    portable_linux_start = 'pwsh -File "$demo_dir/manage-java-services.ps1"'
    portable_linux_start += ' -Action Start -EnvFile "$env_file"'
    assert portable_linux_start in readme
    assert "pinned public images" not in readme
    assert "open `http://localhost:8080/` or" not in readme


def test_java_service_guides_offer_a_policy_safe_native_compose_fallback() -> None:
    root = _read("README.md")
    demo = _read("examples/java-services-demo/README.md")

    assert "If Windows PowerShell blocks scripts" in root
    assert (
        'docker compose -f (Join-Path $demoDir "compose.yaml") -p $project --env-file $envFile '
        "config --quiet"
    ) in root
    assert (
        'docker compose -f (Join-Path $demoDir "compose.yaml") -p $project --env-file $envFile '
        "pull --policy missing"
    ) in root
    assert (
        'docker compose -f (Join-Path $demoDir "compose.yaml") -p $project --env-file $envFile '
        "up -d --wait --wait-timeout 120"
    ) in root
    assert "If Windows PowerShell blocks scripts" in demo
    assert "ConvertFrom-StringData" in demo
    assert "$project = $demoConfig.COMPOSE_PROJECT_NAME" in demo
    assert "$env:DPP_REPO_BASE_URL = $demoConfig.DPP_REPO_BASE_URL" in demo
    assert "$env:DPP_REGISTRY_BASE_URL = $demoConfig.DPP_REGISTRY_BASE_URL" in demo
    assert "docker compose -f $composeFile -p $project --env-file $envFile config --quiet" in demo
    assert (
        "docker compose -f $composeFile -p $project --env-file $envFile pull --policy missing"
        in demo
    )
    assert "docker compose -f $composeFile -p $project --env-file $envFile up -d --wait" in demo
    assert "ExecutionPolicy Bypass" not in root + demo


def test_demo_setup_defines_compose_variables_used_by_operations_reference() -> None:
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")

    compose_file_prefix = "$composeFile = (Resolve-Path "
    compose_file_assignment = (
        compose_file_prefix + ".\\examples\\java-services-demo\\compose.yaml).Path"
    )
    assert compose_file_assignment in demo
    assert 'compose_file="$demo_dir/compose.yaml"' in demo
    assert "$composeFile" in operations
    assert "$compose_file" in operations


def test_documentation_corruption_checks_fail_on_temporary_inputs(tmp_path: Path) -> None:
    temporary = tmp_path / "guide.md"
    temporary.write_text("## Purpose and scope\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        for heading in FAMILIES["docs/model-guide.md"]:
            assert heading in temporary.read_text(encoding="utf-8")

    client = _read("src/dpp_sdk/clients/README.md")
    with pytest.raises(AssertionError):
        _validate_client_operations(client.replace("### delete_dpp_by_id", "### removed_operation"))
    missing_null_behavior = (
        _operation_section(client, "read_dpp_by_id").replace("null", "").replace("Null", "")
    )
    with pytest.raises(AssertionError):
        _validate_operation_section(missing_null_behavior, "read_dpp_by_id")
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
            {"README.md": _read("README.md").replace("Run from:", "")}
        )


def test_installation_and_demo_commands_keep_their_working_directory_contracts() -> None:
    readme = _read("README.md")
    usage = _read("docs/usage.md")
    release = _read("RELEASING.md")
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")

    for text in (readme, usage):
        assert re.search(r"\*\*Run from:\*\* any\s+directory", text)
        assert "directory-independent" in text
    assert "**Run from:** the Python repository root" in readme
    assert "**Run from:** the Python repository root" in release
    assert "from `examples/java-services-demo`" not in demo + operations
    assert "dpp-java-services-demo-$PID" in demo
    assert "COMPOSE_PROJECT_NAME" in demo
    assert 'DPP_REPO_BASE_URL = "http://localhost:18080"' in operations
    assert "DPP_REPO_BASE_URL=http://localhost:18080" in operations
    assert "-Action Delete -ConfirmDelete" in demo
    assert "only the project created by this guide" in demo


def test_command_guides_use_existing_relative_paths_and_separate_shells() -> None:
    readme = _read("README.md")
    release = _read("RELEASING.md")
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")

    for relative in (
        "examples/java-services-demo/compose.yaml",
        "examples/java-services-demo/env/pinned.env",
        "examples/java-services-demo/tests",
    ):
        assert (ROOT / relative).exists(), relative
    assert "~~~powershell" not in demo
    assert "```powershell" in readme
    assert "```bash" in readme
    assert "```powershell" in release
    assert "```bash" in demo
    assert 'python -m build --outdir "$build_root"' in release
    assert "python -m twine check" in release
    assert 'service_script="$demo_dir/manage-java-services.ps1"' in demo
    assert not re.search(r"[A-Za-z]:\\\\", readme + release + demo + operations)


def test_maintained_sdk_only_references_match_the_current_scenario_contract() -> None:
    demo = _read("examples/java-services-demo/README.md")
    changelog = _read("CHANGELOG.md")
    scenario_path = ROOT / "examples/java-services-demo" / "src/dpp_java_services_demo"
    scenarios = (scenario_path / "sdk_scenarios.py").read_text(encoding="utf-8")

    for text in (demo, changelog, scenarios):
        assert "SDK-01 through SDK-17" in text
        assert "SDK-01 through SDK-15" not in text
    assert "EXPECTED_ERROR" in demo


def test_demo_report_commands_use_temporary_output_instead_of_the_worktree() -> None:
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert 'Join-Path ([System.IO.Path]::GetTempPath()) "dpp-java-services-demo-$PID.json"' in demo
    assert 'report="$(mktemp -t dpp-java-services-demo-XXXXXX.json)"' in demo
    assert "examples/java-services-demo/verification-report.json" not in demo + operations
    assert "verification-report.json" in ignored


def test_demo_readme_keeps_cleanup_with_the_live_lifecycle_and_links_operations() -> None:
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")

    assert "[operations reference](OPERATIONS.md)" in demo
    assert "Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue" in demo + operations
    assert 'rm -f "$report"' in demo + operations
    assert "manage-java-services.ps1" in demo
    assert "-Action Start" in demo
    assert "-Action Stop" in demo
    assert "-Action Delete -ConfirmDelete" in demo
    assert demo.count("--run-java-services") == 2
    assert "-c .\\examples\\java-services-demo\\pyproject.toml" in demo
    assert "-c ./examples/java-services-demo/pyproject.toml" in demo


def test_demo_guides_distinguish_modes_and_document_stale_installation_evidence() -> None:
    root = _read("README.md")
    demo = _read("examples/java-services-demo/README.md")
    operations = _read("examples/java-services-demo/OPERATIONS.md")

    assert "SDK-only educational walkthrough" in root
    assert "curated live demonstration" in root
    assert "broad full health" in root
    assert "strict verification" in root
    assert "Copy the complete `examples/java-services-demo` directory" in root
    assert "manage-java-services.ps1" in root
    assert "same-version installation can still be stale" in demo
    assert "pip show dpp-sdk dpp-sdk-java-services-demo" in demo
    assert "Strict verification: NOT_RUN (separate command)." in demo
    assert "Use `--detailed` when you need the full operation evidence." in demo
    assert "Copy `.env.example` to an ignored local `.env`" in demo
    assert "The later Start command pulls" in demo
    assert "missing configured images and starts the services" in demo
    assert "educational JSON evidence" in demo
    assert "Use `verify` for strict package, controlled, and image evidence." in demo
    assert "The same evidence as strict JSON" not in demo
    for text in (demo, operations):
        assert "demo" in text
        assert "full" in text
        assert "verify" in text
        assert "--compose-project" in text


def test_demo_readme_uses_a_goal_led_map_for_canonical_modes() -> None:
    demo = _read("examples/java-services-demo/README.md")

    assert "## Choose your goal" in demo
    assert "Learn the local SDK" in demo
    assert "Present a curated connected workflow" in demo
    assert "Run the broad functional health check" in demo
    assert "Collect exhaustive technical evidence" in demo
    assert "`full --detailed`" in demo
    assert "exact wheels intentionally" in demo
    assert "## Quick command map" not in demo
    assert "The same evidence as strict JSON" not in demo
    assert (
        "Copy `.env.example` to an ignored local `.env` before starting Docker. It pulls"
        not in demo
    )


def test_demo_readme_explains_linux_lifecycle_shell_boundary() -> None:
    demo = _read("examples/java-services-demo/README.md")

    assert "requires PowerShell 7 (`pwsh`) for the labelled lifecycle commands" in demo
    assert "native Docker Compose diagnosis and cleanup commands" in demo
    assert "[operations reference](OPERATIONS.md)" in demo


def test_demo_goal_map_links_resolve_to_step_headings() -> None:
    demo = _read("examples/java-services-demo/README.md")
    headings = re.findall(r"^(#{1,6})\s+(.+)$", demo, re.MULTILINE)
    anchors = set()
    for _, title in headings:
        cleaned_title = re.sub(r"[^a-z0-9 -]", "", title.lower())
        anchors.add("#" + cleaned_title.replace(" ", "-"))
    links = set(re.findall(r"\[[^]]+\]\((#[^)]+)\)", demo))

    for target in (
        "#step-6-run-the-sdk-only-educational-walkthrough",
        "#step-9--run-the-live-integration-educational-walkthrough",
        "#step-10--run-optional-technical-modes",
    ):
        assert target in anchors
        assert target in links
