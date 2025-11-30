from __future__ import annotations

import asyncio
import os
from datetime import datetime
from functools import cached_property
from typing import Literal, TypeAlias

import httpx
import structlog
from pydantic import BaseModel, SecretStr
from whenever import ZonedDateTime

logger = structlog.stdlib.get_logger()


class Config(BaseModel):
    QLD_TRAFFIC_BASE_URL: str = "https://api.qldtraffic.qld.gov.au/v2/"
    QLD_TRAFFIC_API_KEY: SecretStr

    HOME_ASSISTANT_BASE_URL: str
    HOME_ASSISTANT_ACCESS_TOKEN: SecretStr

    # comma separated
    RELEVANT_POSTCODES: str
    RELEVANT_SUBURBS: str

    @staticmethod
    def from_env() -> Config:
        return Config.model_validate(os.environ)

    @cached_property
    def relevant_postcodes(self) -> set[int]:
        return {int(p) for p in self.RELEVANT_POSTCODES.split(",")}

    @cached_property
    def relevant_suburbs(self) -> set[str]:
        return {s.strip().lower() for s in self.RELEVANT_SUBURBS.split(",")}


Status: TypeAlias = Literal["Published"]  # TODO


class Impact(BaseModel):
    impact_type: str
    impact_subtype: str | None
    delay: str | None


class RoadSummary(BaseModel):
    road_name: str | None
    locality: str | None
    postcode: str
    local_government_area: str


class Properties(BaseModel):
    area_alert: bool
    status: Status | str  # TODO
    published: datetime | None
    event_type: str
    event_subtype: str
    impact: Impact
    event_priority: str
    road_summary: RoadSummary


class Event(BaseModel):
    properties: Properties


class EventsResponse(BaseModel):
    features: list[Event]


def parse_postcode(postcodes: str) -> list[int]:
    if postcodes == "-":
        return []

    return [int(p) for p in postcodes.split(" / ") if p.isdigit()]


async def fetch_events(traffic_client: httpx.AsyncClient) -> EventsResponse:
    response = await traffic_client.get("/events")

    response.raise_for_status()

    return EventsResponse.model_validate_json(response.text)


def is_relevant_event(config: Config, event: Event) -> bool:
    postcodes_parsed = parse_postcode(event.properties.road_summary.postcode)

    if any(p in config.relevant_postcodes for p in postcodes_parsed):
        return True

    return False


async def notify_home_assistant(
    ha_client: httpx.AsyncClient,
    relevant_events: list[Event],
):
    most_relevant_event, *rest = relevant_events

    most_relevant_event_summary = f"{most_relevant_event.properties.event_subtype}"

    description = most_relevant_event_summary + (
        f" + {len(rest)} more" if len(rest) > 0 else ""
    )

    res = await ha_client.post(
        "/api/events/traffic_event",
        json={"description": description},
    )

    res.raise_for_status()


async def main(config: Config):
    executed_at = ZonedDateTime.now("Australia/Brisbane")

    async with (
        httpx.AsyncClient(
            base_url=config.QLD_TRAFFIC_BASE_URL,
            params={"apikey": config.QLD_TRAFFIC_API_KEY.get_secret_value()},
        ) as traffic_client,
        httpx.AsyncClient(
            base_url=config.HOME_ASSISTANT_BASE_URL,
            headers={
                "Authorization": f"Bearer {config.HOME_ASSISTANT_ACCESS_TOKEN.get_secret_value()}"
            },
        ) as ha_client,
    ):
        events = await fetch_events(traffic_client=traffic_client)

        relevant_events = [
            e for e in events.features if is_relevant_event(config=config, event=e)
        ]

        if len(relevant_events) == 0:
            logger.info(
                "no relevant events found",
                executed_at=executed_at.format_iso(unit="second", tz="never"),
            )
            return

        print(relevant_events)

        await notify_home_assistant(
            ha_client=ha_client,
            relevant_events=relevant_events,
        )


if __name__ == "__main__":
    config = Config.from_env()

    asyncio.run(main(config=config))
