"""Errors for chat-session application workflows."""


class ChatServiceError(Exception):
    """Transport-agnostic error for chat-session workflows."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
