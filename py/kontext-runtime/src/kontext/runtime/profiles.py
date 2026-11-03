"""Runtime-profile selection for API and console bootstrapping."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Literal

from kontext.common import LOCAL_DEFAULT_SITE_FEATURES, SiteFeature
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.local.config import (
    configure_local_runtime,
    get_local_site_config,
    is_local_mode,
)
from kontext.schema import SiteConfigResponse

#: Supported identity backends per deployment profile.
IdentityBackend = Literal["local_identity", "jwt_distributed"]
#: Supported relational stores per deployment profile.
RelationalBackend = Literal["sqlite", "external"]
#: Supported object/file stores per deployment profile.
StorageBackend = Literal["local_filesystem", "external"]
#: Supported execution topologies. The kernel process is deployment-agnostic.
ExecutionBackend = Literal["kernel_process"]

#: Comma-separated list of extra site feature flags to enable on any profile.
SITE_FEATURES_ENV_VAR = "KONTEXT_SITE_FEATURES"
#: Comma-separated list of site feature flags to disable on any profile. Takes
#: precedence over :data:`SITE_FEATURES_ENV_VAR` so an operator can slim a
#: deployment (for example drop model connections from a shared install)
#: without a code change.
DISABLED_SITE_FEATURES_ENV_VAR = "KONTEXT_DISABLED_SITE_FEATURES"


def _parse_features_env(name: str) -> frozenset[SiteFeature]:
    """Parse a comma-separated feature env var into a set of known features."""
    raw = os.getenv(name, "")
    features: set[SiteFeature] = set()
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            features.add(SiteFeature(value))
        except ValueError:
            # Ignore unknown tokens so a stale flag cannot crash the server.
            continue
    return frozenset(features)


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """Describes how the platform is composed for a given deployment profile."""

    name: str
    is_local: bool
    identity_backend: IdentityBackend
    relational_backend: RelationalBackend
    storage_backend: StorageBackend
    execution_backend: ExecutionBackend
    exposes_local_platform_routers: bool
    #: Deployment capabilities this profile advertises. Both the frontend
    #: (navigation/route visibility) and the backend (``require_site_feature``)
    #: read from here. Distinct from per-user permissions and per-project
    #: ``ProjectFeature`` checks.
    site_features: frozenset[SiteFeature] = dataclass_field(default_factory=frozenset)

    def configure_process_environment(
        self,
        *,
        log_level: str | None = None,
        log_format: str | None = None,
    ) -> str | None:
        if not self.is_local:
            return None
        return configure_local_runtime(log_level=log_level, log_format=log_format)

    def initialize(
        self,
        *,
        log_level: str | None = None,
        log_format: str | None = None,
    ) -> str | None:
        if self.is_local:
            return initialize_local_mode(log_level=log_level, log_format=log_format)

        # Cloud is a documented extension point only; no concrete backend
        # ships in this repository. Add it behind this seam rather than
        # unverified code. The kernel itself is deployment-agnostic.
        raise NotImplementedError(
            "The cloud runtime profile is not implemented. Kontext ships "
            "local-first; extend RuntimeProfile for hosted backends."
        )

    def effective_site_features(self) -> frozenset[SiteFeature]:
        """Return the profile's features with environment overrides applied.

        Enabled features are added; disabled features are then removed (disable
        wins) so a deployment can slim a profile without a code change.
        """
        enabled = _parse_features_env(SITE_FEATURES_ENV_VAR)
        disabled = _parse_features_env(DISABLED_SITE_FEATURES_ENV_VAR)
        return (self.site_features | enabled) - disabled

    def has_feature(self, feature: SiteFeature) -> bool:
        """Return whether this profile advertises ``feature``."""
        return feature in self.effective_site_features()

    def get_site_config(self) -> SiteConfigResponse:
        if self.is_local:
            config = get_local_site_config()
            # Advertise the profile's effective features (env overrides included)
            # so the frontend and backend agree on what is enabled. Sorted for a
            # stable response payload.
            config.features = sorted(feature.value for feature in self.effective_site_features())
            return config

        raise RuntimeError(f"Runtime profile '{self.name}' does not expose local site config")


_LOCAL_RUNTIME_PROFILE = RuntimeProfile(
    name="local",
    is_local=True,
    identity_backend="local_identity",
    relational_backend="sqlite",
    storage_backend="local_filesystem",
    execution_backend="kernel_process",
    exposes_local_platform_routers=True,
    site_features=LOCAL_DEFAULT_SITE_FEATURES,
)

#: Non-local (cloud/hosted) composition. This is a **contract placeholder**, not
#: an implemented backend: it exists so the identity/routing split (JWT vs local
#: identity) stays selectable and testable. No cloud executor, queue worker or
#: managed database ships in this repository; kontext-labs runs the same kernel
#: in a hosted container as it does locally, so ``execution_backend`` is the
#: same process-isolated kernel either way.
_CLOUD_RUNTIME_PROFILE = RuntimeProfile(
    name="cloud",
    is_local=False,
    identity_backend="jwt_distributed",
    relational_backend="external",
    storage_backend="external",
    execution_backend="kernel_process",
    exposes_local_platform_routers=False,
)


def get_runtime_profile() -> RuntimeProfile:
    """Return the active runtime profile.

    Kontext ships local-first. Selection is environment-driven so the
    local/cloud identity split remains a supported contract; only the local
    profile has an implemented composition today.
    """
    return _LOCAL_RUNTIME_PROFILE if is_local_mode() else _CLOUD_RUNTIME_PROFILE


def get_local_runtime_profile() -> RuntimeProfile:
    """Return the local runtime profile."""
    return _LOCAL_RUNTIME_PROFILE


def get_cloud_runtime_profile() -> RuntimeProfile:
    """Return the hosted runtime profile.

    Public on purpose: the offline OpenAPI exporter builds the cloud contract
    with this profile instead of mutating process environment variables.
    """
    return _CLOUD_RUNTIME_PROFILE
