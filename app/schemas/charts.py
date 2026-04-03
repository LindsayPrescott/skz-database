from datetime import date
from typing import Optional
from pydantic import BaseModel


class ChartEntryResponse(BaseModel):
    id: int
    entity_type: str
    release_id: Optional[int] = None
    song_id: Optional[int] = None
    chart_name: str
    chart_region: Optional[str] = None
    peak_position: Optional[int] = None
    chart_date: Optional[date] = None
    certifications: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class ReleaseSalesResponse(BaseModel):
    id: int
    release_id: int
    region: str
    quantity: Optional[int] = None
    sale_type: str
    as_of_date: Optional[date] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
