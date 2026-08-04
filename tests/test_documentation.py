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
    "docs/architecture/diagram-evidence.md",
    "src/dpp_sdk/core/README.md",
    "src/dpp_sdk/dpp4fun/README.md",
    "src/dpp_sdk/clients/README.md",
    "examples/java-services-demo/README.md",
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
    "docs/architecture/diagram-evidence.md",
    "src/dpp_sdk/core/README.md",
    "src/dpp_sdk/dpp4fun/README.md",
    "src/dpp_sdk/clients/README.md",
    "examples/java-services-demo/README.md",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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
        "examples/java-services-demo/README.md",
        _read("examples/java-services-demo/README.md"),
    )
    assert "from `examples/java-services-demo`" not in demo
    assert "docker compose -f $composeFile" in demo
    assert 'docker compose -f "$compose_file"' in demo


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

    for text in (readme, usage):
        assert re.search(r"\*\*Run from:\*\* any\s+directory", text)
        assert "directory-independent" in text
    assert "**Run from:** the Python repository root" in readme
    assert "**Run from:** the Python repository root" in release
    assert "from `examples/java-services-demo`" not in demo
    assert "dpp-java-services-demo-$PID" in demo
    assert "dpp-java-services-demo-$$" in demo
    assert "$repoUrl = if ($env:DPP_REPO_BASE_URL)" in demo
    assert 'repo_url="${DPP_REPO_BASE_URL:-http://localhost:8080}"' in demo
    assert "down --volumes --remove-orphans" in demo
    assert "only the project created by this guide" in demo


def test_command_guides_use_existing_relative_paths_and_separate_shells() -> None:
    readme = _read("README.md")
    release = _read("RELEASING.md")
    demo = _read("examples/java-services-demo/README.md")

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
    assert 'compose_file="$demo_dir/compose.yaml"' in demo
    assert not re.search(r"[A-Za-z]:\\\\", readme + release + demo)
