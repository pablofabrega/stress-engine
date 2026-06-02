from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message envelope for endpoints without a richer payload."""

    detail: str
