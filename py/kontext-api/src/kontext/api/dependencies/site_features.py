"""Site-feature gating dependencies.

``require_site_feature`` mirrors :func:`kontext.api.dependencies.auth.create_auth_dependency`
but gates on *deployment capability* rather than per-user permissions. Use it
when a route should only be served by deployments that advertise the relevant
:class:`~kontext.common.SiteFeature`.

This is distinct from:

- ``SiteFeature`` route/nav visibility on the frontend (cosmetic), and
- ``ProjectFeature`` checks (per-project capability), and
- permission checks (per-user authorization).

A route gated here is refused server-side, so hiding the surface in the UI is a
convenience rather than the only line of defence.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

from kontext.common import SiteFeature
from kontext.runtime.profiles import get_runtime_profile


def require_site_feature(*features: SiteFeature, require_all: bool = False):
    """Return a FastAPI dependency enforcing one or more site features.

    Args:
        *features: Feature flags the active deployment must advertise.
        require_all: When ``True`` every feature must be enabled; otherwise any
            one of them is sufficient.

    Raises:
        HTTPException: ``404`` when the feature is not enabled. A 404 (rather
            than 403) keeps a disabled surface indistinguishable from a
            non-existent one, so the API shape does not leak deployment detail.
    """

    def _check() -> None:
        enabled = get_runtime_profile().effective_site_features()
        if not features:
            return
        allowed = (
            all(feature in enabled for feature in features)
            if require_all
            else bool(enabled.intersection(features))
        )
        if not allowed:
            raise HTTPException(status_code=404, detail="Not found")

    return Depends(_check)


__all__ = ["require_site_feature"]
