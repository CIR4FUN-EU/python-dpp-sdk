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


def _runtime_digest(image: str, runner: CommandRunner) -> str:
    output = runner(("docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"))
    try:
        repo_digests = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ImageInspectionError(f"runtime digest output was not JSON: {output!r}") from exc
    if not isinstance(repo_digests, list):
        raise ImageInspectionError("runtime digest output was not a list")
    expected_repository = image.partition("@")[0].rsplit(":", maxsplit=1)[0]
    matches = [
        digest.rpartition("@")[2]
        for digest in repo_digests
        if isinstance(digest, str) and digest.startswith(f"{expected_repository}@")
    ]
    if len(matches) != 1 or _DIGEST_PATTERN.fullmatch(matches[0]) is None:
        raise ImageInspectionError(f"could not resolve one runtime digest for {image}")
    return matches[0].lower()


def _remote_digest(image: str, runner: CommandRunner) -> str:
    output = runner(("docker", "buildx", "imagetools", "inspect", image))
    matches = _DIGEST_PATTERN.findall(output)
    if not matches:
        raise ImageInspectionError(f"could not resolve remote digest for {image}")
    return matches[0].lower()


def capture_image_identities(
    config: DemoConfig,
    *,
    runner: CommandRunner = _run_command,
) -> ImageIdentityReport:
    """Inspect local runtime images and freshly resolve maintained 0.5.0 tags."""

    repo_runtime = _runtime_digest(config.repo_image, runner)
    registry_runtime = _runtime_digest(config.registry_image, runner)
    maintained_repo = _remote_digest(_MAINTAINED_REPO_IMAGE, runner)
    maintained_registry = _remote_digest(_MAINTAINED_REGISTRY_IMAGE, runner)
    same_build = repo_runtime == maintained_repo and registry_runtime == maintained_registry
    return ImageIdentityReport(
        repo_runtime_digest=repo_runtime,
        registry_runtime_digest=registry_runtime,
        maintained_repo_digest=maintained_repo,
        maintained_registry_digest=maintained_registry,
        equivalence=(
            ImageEquivalence.SAME_BUILD if same_build else ImageEquivalence.DIFFERENT_BUILD
        ),
    )
