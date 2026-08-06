from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.image_identity import (
    ImageEquivalence,
    ImageInspectionError,
    capture_image_identities,
    capture_runtime_image_identities,
)

REPO_DIGEST = "sha256:bf36c904a7af28bdf8c08c774007b0c224137b31bcbe92e70647f1386bd5a04a"
REGISTRY_DIGEST = "sha256:3d25555e08c05f3462e45e8bc3f11b1bddd8d01541d7dfabd3240b8c03ca9560"


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image=f"ghcr.io/cir4fun-eu/dpp-repo-api:sha-current@{REPO_DIGEST}",
        registry_image=f"ghcr.io/cir4fun-eu/dpp-registry-api:sha-current@{REGISTRY_DIGEST}",
        env_file=Path("env/pinned.env"),
        startup_timeout_seconds=120,
        legacy=False,
    )


def _runner(command: Sequence[str]) -> str:
    joined = " ".join(command)
    if command[1] == "ps":
        return "repo-container" if "dpp-repo-api" in joined else "registry-container"
    if command[1] == "inspect" and ".Config.Image" in joined:
        return _config().repo_image if "repo-container" in joined else _config().registry_image
    if command[1] == "inspect" and ".Image" in joined:
        return "sha256:" + (("c" if "repo-container" in joined else "d") * 64)
    if tuple(command[1:3]) == ("image", "inspect"):
        digest = REPO_DIGEST if ("c" * 64) in joined else REGISTRY_DIGEST
        repository = "dpp-repo-api" if ("c" * 64) in joined else "dpp-registry-api"
        return f'["ghcr.io/cir4fun-eu/{repository}@{digest}"]'
    digest = REPO_DIGEST if "repo-api" in joined else REGISTRY_DIGEST
    return f"Name: example\nDigest: {digest}\n"


def test_capture_records_runtime_and_fresh_maintained_digests() -> None:
    report = capture_image_identities(_config(), compose_project="test-project", runner=_runner)

    assert report.repo_container_id == "repo-container"
    assert report.registry_container_id == "registry-container"
    assert report.repo_runtime_digest == REPO_DIGEST
    assert report.registry_runtime_digest == REGISTRY_DIGEST
    assert report.maintained_repo_digest == REPO_DIGEST
    assert report.maintained_registry_digest == REGISTRY_DIGEST
    assert report.equivalence is ImageEquivalence.SAME_BUILD


def test_runtime_capture_reports_serving_digests_without_remote_lookup() -> None:
    commands: list[tuple[str, ...]] = []

    def runtime_only_runner(command: Sequence[str]) -> str:
        commands.append(tuple(command))
        return _runner(command)

    report = capture_runtime_image_identities(
        _config(), compose_project="test-project", runner=runtime_only_runner
    )

    assert report.repo_runtime_digest == REPO_DIGEST
    assert report.registry_runtime_digest == REGISTRY_DIGEST
    assert not any(command[1:3] == ("buildx", "imagetools") for command in commands)


def test_capture_classifies_changed_maintained_image() -> None:
    def changed_runner(command: Sequence[str]) -> str:
        if tuple(command[1:4]) == ("buildx", "imagetools", "inspect"):
            return "Name: example\nDigest: sha256:" + ("a" * 64)
        return _runner(command)

    report = capture_image_identities(
        _config(), compose_project="test-project", runner=changed_runner
    )

    assert report.equivalence is ImageEquivalence.DIFFERENT_BUILD


def test_missing_digest_is_an_explicit_inspection_failure() -> None:
    def missing_digest_runner(command: Sequence[str]) -> str:
        if tuple(command[1:3]) == ("image", "inspect"):
            return "[]"
        return _runner(command)

    with pytest.raises(ImageInspectionError, match="digest"):
        capture_image_identities(
            _config(),
            compose_project="test-project",
            runner=missing_digest_runner,
        )


def test_container_must_use_the_configured_image_reference() -> None:
    def mismatched_runner(command: Sequence[str]) -> str:
        if command[1] == "inspect" and ".Config.Image" in " ".join(command):
            return "ghcr.io/example/unrelated:latest"
        return _runner(command)

    with pytest.raises(ImageInspectionError, match="configured image"):
        capture_image_identities(
            _config(),
            compose_project="test-project",
            runner=mismatched_runner,
        )
