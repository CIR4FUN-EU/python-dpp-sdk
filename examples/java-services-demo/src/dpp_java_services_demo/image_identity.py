"""Runtime and maintained Java image identity evidence."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .config import DemoConfig

_MAINTAINED_REPO_IMAGE = "ghcr.io/cir4fun-eu/dpp-repo-api:0.5.0"
_MAINTAINED_REGISTRY_IMAGE = "ghcr.io/cir4fun-eu/dpp-registry-api:0.5.0"
_DIGEST_PATTERN = re.compile(r"\bsha256:[0-9a-fA-F]{64}\b")
CommandRunner = Callable[[Sequence[str]], str]


class ImageInspectionError(RuntimeError):
    """Docker could not supply an unambiguous image digest."""


class ImageEquivalence(StrEnum):
    SAME_BUILD = "SAME_BUILD"
    DIFFERENT_BUILD = "DIFFERENT_BUILD"


@dataclass(frozen=True)
class ImageIdentityReport:
    repo_container_id: str
    registry_container_id: str
    repo_container_image_id: str
    registry_container_image_id: str
    repo_runtime_digest: str
    registry_runtime_digest: str
    maintained_repo_digest: str
    maintained_registry_digest: str
    equivalence: ImageEquivalence


def _run_command(command: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "")
        detail = str(stderr).strip() or str(exc)
        raise ImageInspectionError(f"image inspection command failed: {detail}") from exc
    return completed.stdout


def _runtime_digest(image_id: str, configured_image: str, runner: CommandRunner) -> str:
    output = runner(("docker", "image", "inspect", image_id, "--format", "{{json .RepoDigests}}"))
    try:
        repo_digests = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ImageInspectionError(f"runtime digest output was not JSON: {output!r}") from exc
    if not isinstance(repo_digests, list):
        raise ImageInspectionError("runtime digest output was not a list")
    expected_repository = configured_image.partition("@")[0].rsplit(":", maxsplit=1)[0]
    matches = [
        digest.rpartition("@")[2]
        for digest in repo_digests
        if isinstance(digest, str) and digest.startswith(f"{expected_repository}@")
    ]
    if len(matches) != 1 or _DIGEST_PATTERN.fullmatch(matches[0]) is None:
        raise ImageInspectionError(f"could not resolve one runtime digest for {configured_image}")
    return matches[0].lower()


def _container_identity(
    compose_project: str,
    service: str,
    configured_image: str,
    runner: CommandRunner,
) -> tuple[str, str, str]:
    output = runner(
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "--format",
            "{{.ID}}",
        )
    )
    container_ids = tuple(line.strip() for line in output.splitlines() if line.strip())
    if len(container_ids) != 1:
        raise ImageInspectionError(
            f"expected one running {service} container in project {compose_project}, "
            f"found {len(container_ids)}"
        )
    container_id = container_ids[0]
    actual_reference = runner(
        ("docker", "inspect", container_id, "--format", "{{.Config.Image}}")
    ).strip()
    if actual_reference != configured_image:
        raise ImageInspectionError(
            f"{service} container does not use the configured image: {actual_reference}"
        )
    image_id = runner(("docker", "inspect", container_id, "--format", "{{.Image}}")).strip()
    if _DIGEST_PATTERN.fullmatch(image_id) is None:
        raise ImageInspectionError(f"{service} container image ID is not a sha256 digest")
    runtime_digest = _runtime_digest(image_id, configured_image, runner)
    return container_id, image_id.lower(), runtime_digest


def _remote_digest(image: str, runner: CommandRunner) -> str:
    output = runner(("docker", "buildx", "imagetools", "inspect", image))
    matches = _DIGEST_PATTERN.findall(output)
    if not matches:
        raise ImageInspectionError(f"could not resolve remote digest for {image}")
    return matches[0].lower()


def capture_image_identities(
    config: DemoConfig,
    *,
    compose_project: str,
    runner: CommandRunner = _run_command,
) -> ImageIdentityReport:
    """Bind serving Compose containers to images and freshly resolve maintained tags."""

    if not compose_project.strip():
        raise ImageInspectionError("a non-blank Compose project is required")
    repo_container, repo_image_id, repo_runtime = _container_identity(
        compose_project,
        "dpp-repo-api",
        config.repo_image,
        runner,
    )
    registry_container, registry_image_id, registry_runtime = _container_identity(
        compose_project,
        "dpp-registry-api",
        config.registry_image,
        runner,
    )
    maintained_repo = _remote_digest(_MAINTAINED_REPO_IMAGE, runner)
    maintained_registry = _remote_digest(_MAINTAINED_REGISTRY_IMAGE, runner)
    same_build = repo_runtime == maintained_repo and registry_runtime == maintained_registry
    return ImageIdentityReport(
        repo_container_id=repo_container,
        registry_container_id=registry_container,
        repo_container_image_id=repo_image_id,
        registry_container_image_id=registry_image_id,
        repo_runtime_digest=repo_runtime,
        registry_runtime_digest=registry_runtime,
        maintained_repo_digest=maintained_repo,
        maintained_registry_digest=maintained_registry,
        equivalence=(
            ImageEquivalence.SAME_BUILD if same_build else ImageEquivalence.DIFFERENT_BUILD
        ),
    )
