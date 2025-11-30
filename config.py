from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import BaseModel, SecretStr

import models


class Config(BaseModel):
    QLD_TRAFFIC_BASE_URL: str = "https://api.qldtraffic.qld.gov.au/v2/"
    QLD_TRAFFIC_API_KEY: SecretStr

    HOME_ASSISTANT_BASE_URL: str
    HOME_ASSISTANT_ACCESS_TOKEN: SecretStr

    NOTIFIED_EVENTS_PATH: Path = Path("notified.json")

    # comma separated
    RELEVANT_POSTCODES: str | None = None
    RELEVANT_SUBURBS: str | None = None
    RELEVANT_TOWARDS_SUBURBS: str | None = None
    RELEVANT_EVENT_TYPES: str | None = None

    @staticmethod
    def from_env() -> Config:
        return Config.model_validate(os.environ)


DEFAULT_RELEVANT_EVENT_TYPES: set[models.EventType] = {
    "Congestion",
    "Crash",
    "Flooding",
    "Hazard",
    "Roadworks",
}


@dataclass(frozen=True)
class EventRelevancyConfig:
    types: set[models.EventType]
    postcodes: set[int]
    suburbs: set[str]
    towards_suburbs: set[str]

    @staticmethod
    def from_config(config: Config) -> EventRelevancyConfig:
        types: set[models.EventType] = (
            {cast(models.EventType, t) for t in config.RELEVANT_EVENT_TYPES.split(",")}
            if config.RELEVANT_EVENT_TYPES is not None
            else DEFAULT_RELEVANT_EVENT_TYPES
        )
        postcodes = (
            {int(p) for p in config.RELEVANT_POSTCODES.split(",")}
            if config.RELEVANT_POSTCODES is not None
            else set()
        )
        suburbs = (
            {s.strip() for s in config.RELEVANT_SUBURBS.split(",")}
            if config.RELEVANT_SUBURBS is not None
            else set()
        )
        towards_suburbs = (
            {s.strip() for s in config.RELEVANT_TOWARDS_SUBURBS.split(",")}
            if config.RELEVANT_TOWARDS_SUBURBS is not None
            else set()
        )

        return EventRelevancyConfig(
            types=types,
            postcodes=postcodes,
            suburbs=suburbs,
            towards_suburbs=towards_suburbs,
        )


@dataclass
class NotifiedEvents:
    path: Path
    model: NotifiedEvents.Model

    class Model(BaseModel):
        events: list[models.NotifiedEvent]
        version: int

    @property
    def events(self) -> list[models.NotifiedEvent]:
        return self.model.events

    @staticmethod
    def from_config(config: Config) -> NotifiedEvents:
        if not (path := config.NOTIFIED_EVENTS_PATH).exists():
            path.touch()

            return NotifiedEvents(
                path=path, model=NotifiedEvents.Model(events=[], version=1)
            )

        return NotifiedEvents(
            path=path, model=NotifiedEvents.Model.model_validate_json(path.read_text())
        )

    def contains(self, event: models.Event) -> bool:
        return any(ne.event_id == event.id for ne in self.model.events)

    def append_event(self, event: models.Event, reason: str) -> None:
        self.model.events.append(models.NotifiedEvent(event_id=event.id, reason=reason))

        self.path.write_text(self.model.model_dump_json(indent=2))
