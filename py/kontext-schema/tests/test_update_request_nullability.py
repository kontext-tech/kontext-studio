from __future__ import annotations

import pytest
from pydantic import ValidationError

from kontext.schema import (
    QuerySessionStatus,
    UpdateChatSessionRequest,
    UpdateQuerySessionRequest,
)


def test_update_query_session_request_omits_none_values_from_payload():
    # Omitting optional non-nullable fields should produce an empty payload
    request = UpdateQuerySessionRequest()

    assert request.to_dict() == {}


def test_update_query_session_request_serializes_values_normally():
    request = UpdateQuerySessionRequest(status=QuerySessionStatus.CLOSED)

    assert request.to_dict() == {"status": QuerySessionStatus.CLOSED}


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"sessionName": None}, "sessionName"),
        ({"defaultNamespace": None}, "defaultNamespace"),
    ],
)
def test_update_chat_session_request_rejects_non_clearable_nulls(payload, field_name):
    with pytest.raises(ValidationError, match=field_name):
        UpdateChatSessionRequest.from_dict(payload)
