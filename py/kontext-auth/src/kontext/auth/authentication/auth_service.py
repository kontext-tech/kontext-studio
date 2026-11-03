"""Authentication service for host-api auth calls."""

from __future__ import annotations

import httpx

from kontext.schema import AccessTokenResponse


class AuthService:
    """Small HTTP client for the Kontext host auth contract."""

    def __init__(self, api_base_url: str, timeout_seconds: int = 60):
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def refresh_user_token(self, refresh_token: str) -> AccessTokenResponse:
        response = httpx.post(
            f"{self.api_base_url}/host/auth/refresh",
            json={"refreshToken": refresh_token},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token_payload = payload.get("accessToken", payload)
        return AccessTokenResponse.model_validate(token_payload)
