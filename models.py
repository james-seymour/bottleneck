from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel

Status: TypeAlias = Literal["Published"]

ImpactType: TypeAlias = Literal[
    "Closures",
    "Lanes affected",
    "Lanes blocked",
    "N/A",
    "No blockage",
    "Road restricted",
]


class Impact(BaseModel):
    impact_type: ImpactType | str
    impact_subtype: str | None
    towards: str | None
    delay: str | None


class Duration(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class RoadSummary(BaseModel):
    road_name: str | None
    locality: str | None
    postcode: str
    local_government_area: str
    district: str


EventType: TypeAlias = Literal[
    "Congestion",
    "Crash",
    "Flooding",
    "Hazard",
    "Roadworks",
    "Special Event",
]

EventSubtype: TypeAlias = Literal[
    "Adverse driving conditions",
    "Bridge or culvert damaged",
    "Debris on road",
    "Emergency roadworks",
    "Fire",
    "Flash flooding",
    "General",
    "Long-term flooding",
    "Multi-vehicle",
    "N/A",
    "Planned roadworks",
    "Recurring",
    "Road damage",
    "Signal fault",
    "Stationary vehicle",
]


class Event(BaseModel):
    id: int
    area_alert: bool
    status: Status | str
    published: datetime | None
    event_type: EventType | str
    event_subtype: EventSubtype | str
    event_priority: Literal["Low", "Medium", "High"]
    impact: Impact
    duration: Duration
    road_summary: RoadSummary


class Feature(BaseModel):
    properties: Event


class EventsResponse(BaseModel):
    features: list[Feature]


class NotifiedEvent(BaseModel):
    event_id: int
    reason: str
