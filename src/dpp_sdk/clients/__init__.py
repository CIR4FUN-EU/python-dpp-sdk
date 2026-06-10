"""HTTP clients for the DPP repository and registry APIs (prEN-18222-aligned).

Port of `dpp.repo.client.*` / `dpp.registry.client.*` from
../dpp-sdk-platform/dpp-sdk-clients.
"""

from ._http import DppCodec, DppValidator
from .endpoints import (
    DEFAULT_REGISTRY_BASE_URL,
    DEFAULT_REGISTRY_PORT,
    DEFAULT_REPO_BASE_URL,
    DEFAULT_REPO_PORT,
    local_registry_base_url,
    local_repo_base_url,
)
from .errors import (
    DppApiClientError,
    DppClientError,
    DppHttpClientError,
    DppMappingClientError,
    DppNetworkClientError,
    DppValidationClientError,
)
from .payloads import (
    CreateDppResponse,
    DeleteDppResponse,
    DppApiMessage,
    DppApiResponse,
    DppStatusCode,
    MessageType,
    ReadDppIdsRequest,
    ReadDppIdsResponse,
    RegisterDppRequest,
    RegisterDppResponse,
    UpdateDataElementRequest,
)
from .registry import DppRegistryClient
from .repo import DppRepoClient

__all__ = [
    "DEFAULT_REGISTRY_BASE_URL",
    "DEFAULT_REGISTRY_PORT",
    "DEFAULT_REPO_BASE_URL",
    "DEFAULT_REPO_PORT",
    "CreateDppResponse",
    "DeleteDppResponse",
    "DppApiClientError",
    "DppApiMessage",
    "DppApiResponse",
    "DppClientError",
    "DppCodec",
    "DppHttpClientError",
    "DppMappingClientError",
    "DppNetworkClientError",
    "DppRegistryClient",
    "DppRepoClient",
    "DppStatusCode",
    "DppValidationClientError",
    "DppValidator",
    "MessageType",
    "ReadDppIdsRequest",
    "ReadDppIdsResponse",
    "RegisterDppRequest",
    "RegisterDppResponse",
    "UpdateDataElementRequest",
    "local_registry_base_url",
    "local_repo_base_url",
]
