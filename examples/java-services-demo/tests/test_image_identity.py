from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.image_identity import (
    ImageEquivalence,
    ImageInspectionError,
    capture_image_identities,
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
    if tuple(command[1:3]) == ("image", "inspect"):
        digest = REPO_DIGEST if "repo-api" in joined else REGISTRY_DIGEST
        repository = "dpp-repo-api" if "repo-api" in joined else "dpp-registry-api"
        return f'["ghcr.io/cir4fun-eu/{repository}@{digest}"]'
    digest = REPO_DIGEST if "repo-api" in joined else REGISTRY_DIGEST
    return f"Name: example\nDigest: {digest}\n"


def test_capture_records_runtime_and_fresh_maintained_digests() -> None:
    report = capture_image_identities(_config(), runner=_runner)

    assert report.repo_runtime_digest == REPO_DIGEST
    assert report.registry_runtime_digest == REGISTRY_DIGEST
    assert report.maintained_repo_digest == REPO_DIGEST
    assert report.maintained_registry_digest == REGISTRY_DIGEST
    assert report.equivalence is ImageEquivalence.SAME_BUILD


def test_capture_classifies_changed_maintained_image() -> None:
    def changed_runner(command: Sequence[str]) -> str:
        if tuple(command[1:3]) == ("image", "inspect"):
            return _runner(command)
        return "Name: example\nDigest: sha256:" + ("a" * 64)

    report = capture_image_identities(_config(), runner=changed_runner)

    assert report.equivalence is ImageEquivalence.DIFFERENT_BUILD


def test_missing_digest_is_an_explicit_inspection_failure() -> None:
    with pytest.raises(ImageInspectionError, match="digest"):
        capture_image_identities(_config(), runner=lambda _command: "Name: example")
