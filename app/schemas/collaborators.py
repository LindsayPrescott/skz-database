from typing import Optional
from pydantic import BaseModel

from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse


class CollaboratorResponse(BaseModel):
    id: int
    name: str
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CollaboratorDetailResponse(CollaboratorResponse):
    roles: dict[str, int] = {}


class CollaboratorReleasesPage(Page[ReleaseResponse]):
    collaborator: CollaboratorResponse
