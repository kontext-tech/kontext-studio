"""First-run setup endpoints for Kontext local mode."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from kontext.account import is_setup_complete
from kontext.runtime.local.bootstrap import complete_local_setup
from kontext.schema import AccessTokenResponse, SetupRequest, SetupStatusResponse

from ..dependencies.local_auth import build_token_response

router = APIRouter(prefix="/setup", tags=["Setup"])


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status() -> SetupStatusResponse:
    return SetupStatusResponse(is_setup_complete=is_setup_complete())


@router.post("", response_model=AccessTokenResponse)
def complete_setup(request: SetupRequest) -> AccessTokenResponse:
    try:
        profile = complete_local_setup(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return build_token_response(profile)
