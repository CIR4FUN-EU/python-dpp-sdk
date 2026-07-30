from __future__ import annotations

from pathlib import Path

from dpp_java_services_demo.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PINNED_REPO = (
    "ghcr.io/cir4fun-eu/dpp-repo-api:"
    "sha-4d3d280227b8349f4e6fa7af732803976615eef6"
    "@sha256:bf36c904a7af28bdf8c08c774007b0c224137b31bcbe92e70647f1386bd5a04a"
)
PINNED_REGISTRY = (
    "ghcr.io/cir4fun-eu/dpp-registry-api:"
    "sha-4d3d280227b8349f4e6fa7af732803976615eef6"
    "@sha256:3d25555e08c05f3462e45e8bc3f11b1bddd8d01541d7dfabd3240b8c03ca9560"
)


def _profile_values(name: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (PROJECT_ROOT / "env" / name).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", maxsplit=1)
            values[key] = value
    return values


def test_compose_is_two_service_pull_only_memory_mode() -> None:
    text = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert text.count("\n  dpp-repo-api:") == 1
    assert text.count("\n  dpp-registry-api:") == 1
    assert "${DPP_REPO_IMAGE:?set DPP_REPO_IMAGE}" in text
    assert "${DPP_REGISTRY_IMAGE:?set DPP_REGISTRY_IMAGE}" in text
    assert '"${DPP_REPO_PORT:-8080}:8080"' in text
    assert '"${DPP_REGISTRY_PORT:-8081}:8081"' in text
    assert "condition: service_healthy" in text
    assert "DEMO_REPO_PUBLIC_BASE_URL: ${DPP_REPO_BASE_URL:-http://localhost:8080}" in text
    assert "DEMO_REPO_VERIFICATION_BASE_URL: http://dpp-repo-api:8080" in text
    for forbidden in (
        "build:",
        "container_name:",
        "postgres",
        "volumes:",
        "SPRING_DATASOURCE",
        "DPP_REPO_BACKEND",
        "DPP_REGISTRY_BACKEND",
    ):
        assert forbidden not in text


def test_pinned_profile_uses_approved_tag_plus_digest_references() -> None:
    values = _profile_values("pinned.env")

    assert values["DPP_REPO_IMAGE"] == PINNED_REPO
    assert values["DPP_REGISTRY_IMAGE"] == PINNED_REGISTRY
    assert values["DPP_REPO_BASE_URL"] == "http://localhost:8080"
    assert values["DPP_REGISTRY_BASE_URL"] == "http://localhost:8081"


def test_maintained_and_legacy_profiles_have_distinct_policy() -> None:
    maintained = _profile_values("0.5.0.env")
    legacy = _profile_values("0.4.0.env")
    legacy_text = (PROJECT_ROOT / "env" / "0.4.0.env").read_text(encoding="utf-8")

    assert maintained["DPP_REPO_IMAGE"].endswith(":0.5.0")
    assert maintained["DPP_REGISTRY_IMAGE"].endswith(":0.5.0")
    assert legacy["DPP_REPO_IMAGE"].endswith(":0.4.0")
    assert legacy["DPP_REGISTRY_IMAGE"].endswith(":0.4.0")
    assert "optional legacy compatibility" in legacy_text.lower()
    assert "non-blocking" in legacy_text.lower()


def test_default_configuration_is_the_pinned_profile() -> None:
    config = load_config()

    assert config.env_file == (PROJECT_ROOT / "env" / "pinned.env").resolve()
    assert config.repo_image == PINNED_REPO
    assert config.registry_image == PINNED_REGISTRY
