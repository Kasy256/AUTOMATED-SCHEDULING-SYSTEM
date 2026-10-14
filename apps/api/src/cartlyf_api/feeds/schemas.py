from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FeedOut(BaseModel):
    id: UUID
    resource_id: UUID
    created_at: datetime
    revoked_at: datetime | None


class FeedCreated(BaseModel):
    """The feed's URL carries its secret token and is shown only in this response."""

    id: UUID
    resource_id: UUID
    url: str
    created_at: datetime
