from __future__ import annotations

from pathlib import Path

import pytest

from dpp_java_services_demo.config import DemoConfig, load_config

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


def _write_env(path: Path, *, repo_image: str = PINNED_REPO) -> None:
    path.write_text(
        "\n".join(
            (
                f"DPP_REPO_IMAGE={repo_image}",
                f"DPP_REGISTRY_IMAGE={PINNED_REGISTRY}",
                "DPP_REPO_BASE_URL=http://localhost:8080",
                "DPP_REGISTRY_BASE_URL=http://localhost:8081",
                "DPP_STARTUP_TIMEOUT_SECONDS=90",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def test_load_config_reads_explicit_profile(tmp_path: Path) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)

    config = load_config(env_file)

    assert config == DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image=PINNED_REPO,
        registry_image=PINNED_REGISTRY,
        env_file=env_file.resolve(),
        startup_timeout_seconds=90.0,
        legacy=False,
    )


def test_environment_overrides_file_without_mutating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://127.0.0.1:18080")

    config = load_config(env_file)

    assert config.repo_base_url == "http://127.0.0.1:18080"
    assert "127.0.0.1" not in env_file.read_text(encoding="utf-8")


def test_legacy_profile_requires_explicit_flag(tmp_path: Path) -> None:
    env_file = tmp_path / "0.4.0.env"
    _write_env(env_file, repo_image="ghcr.io/cir4fun-eu/dpp-repo-api:0.4.0")

    with pytest.raises(ValueError, match="--legacy"):
        load_config(env_file)

    assert load_config(env_file, legacy=True).legacy is True


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("DPP_REPO_IMAGE=\n", "DPP_REPO_IMAGE"),
        ("DPP_STARTUP_TIMEOUT_SECONDS=zero\n", "DPP_STARTUP_TIMEOUT_SECONDS"),
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, line: str, message: str) -> None:
    env_file = tmp_path / "invalid.env"
    _write_env(env_file)
    contents = env_file.read_text(encoding="utf-8")
    key = line.split("=", maxsplit=1)[0]
    contents = "\n".join(item for item in contents.splitlines() if not item.startswith(f"{key}="))
    env_file.write_text(f"{contents}\n{line}", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_config(env_file)
