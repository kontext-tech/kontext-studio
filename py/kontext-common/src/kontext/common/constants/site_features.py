"""Server-advertised site feature flags.

Mirrors ``SiteFeature`` in ``ts/schema/src/core/domains/base/index.ts``. The
active :class:`~kontext.runtime.profiles.RuntimeProfile` advertises the subset
it supports through :class:`~kontext.schema.SiteConfigResponse`,
and both the frontend (navigation/route visibility) and the backend
(``require_site_feature`` router gating) consume the same values.

These flags describe a *deployment capability*: which surfaces this build
exposes. They are deliberately distinct from per-user permissions and from
per-project ``ProjectFeature`` capability checks.
"""

from enum import StrEnum


class SiteFeature(StrEnum):
    """Site-level feature flags advertised by the runtime profile."""

    #: Real-time notification bell + inbox.
    NOTIFICATIONS = "notifications"
    #: Subscription management (billing / notification groups).
    SUBSCRIPTIONS = "subscriptions"
    #: Password change and 2FA management in Account settings.
    USER_AUTH_MANAGEMENT = "user-auth-management"
    #: Require CAPTCHA on login, register, and forgot-password forms.
    CAPTCHA = "captcha"
    #: Registration requires a valid invitation code.
    INVITATION_REQUIRED = "invitation-required"
    #: App is running in local (self-hosted / offline) mode.
    LOCAL_MODE = "local-mode"
    #: Executable AI model connection management is available.
    MODEL_CONNECTIONS = "model-connections"
    #: Managed Python runtime metadata page is available.
    PYTHON_ENVIRONMENT = "python-environment"


#: Features every local-first deployment advertises. Kept here (rather than in
#: ``kontext-runtime``) so both the local site config and the runtime profile can
#: share one definition without a circular import.
LOCAL_DEFAULT_SITE_FEATURES: frozenset[SiteFeature] = frozenset(
    {
        SiteFeature.LOCAL_MODE,
        SiteFeature.MODEL_CONNECTIONS,
        SiteFeature.PYTHON_ENVIRONMENT,
    }
)
