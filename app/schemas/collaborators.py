from typing import Optional
from pydantic import BaseModel


class CollaboratorResponse(BaseModel):
    id: int
    name: str
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
