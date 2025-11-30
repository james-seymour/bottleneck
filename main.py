from __future__ import annotations

import asyncio
from typing import Literal, TypeAlias

import httpx
import structlog
from whenever import ZonedDateTime

import config
import models
import util

logger = structlog.stdlib.get_logger()


async def fetch_events(traffic_client: httpx.AsyncClient) -> list[models.Event]:
    response = await traffic_client.get("/events")

    response.raise_for_status()

    features = models.EventsResponse.model_validate_json(response.text)

    return [f.properties for f in features.features]


RelevancyReason: TypeAlias = Literal[
    "irrelevant",
    "relevant-postcode",
    "relevant-suburb",
    "relevant-towards",
]


def determine_relevancy(
    relevancy_config: config.EventRelevancyConfig,
    event: models.Event,
) -> RelevancyReason:
    if event.event_type not in relevancy_config.types:
        return "irrelevant"

    postcodes_parsed = util.parse_postcode(event.road_summary.postcode)

    if any(p in relevancy_config.postcodes for p in postcodes_parsed):
        return "relevant-postcode"

    parsed_suburbs = util.parse_suburbs(event.road_summary.locality)

    if any(s in relevancy_config.suburbs for s in parsed_suburbs):
        return "relevant-suburb"

    if event.impact.towards in relevancy_config.towards_suburbs:
        return "relevant-towards"

    return "irrelevant"


async def notify_home_assistant(*, ha_client: httpx.AsyncClient, event: models.Event):
    title = f"{event.event_type} - {event.road_summary.locality}"
    description = f"{event.impact.impact_type} on {event.road_summary.road_name} - {event.impact.delay or 'No delay reported'}"

    res = await ha_client.post(
        "/api/events/traffic_event",
        json={"title": title, "description": description},
    )

    res.raise_for_status()


async def main(cfg: config.Config):
    executed_at = ZonedDateTime.now("Australia/Brisbane")

    traffic_client = httpx.AsyncClient(
        base_url=cfg.QLD_TRAFFIC_BASE_URL,
        params={"apikey": cfg.QLD_TRAFFIC_API_KEY.get_secret_value()},
    )

    ha_client = httpx.AsyncClient(
        base_url=cfg.HOME_ASSISTANT_BASE_URL,
        headers={
            "Authorization": f"Bearer {cfg.HOME_ASSISTANT_ACCESS_TOKEN.get_secret_value()}"
        },
    )

    relevancy_config = config.EventRelevancyConfig.from_config(cfg)
    notified_events = config.NotifiedEvents.from_config(cfg)

    async with traffic_client, ha_client:
        events = await fetch_events(traffic_client=traffic_client)

        relevant_events = [
            (e, r)
            for e in events
            if (r := determine_relevancy(relevancy_config=relevancy_config, event=e))
            != "irrelevant"
        ]

        if len(relevant_events) == 0:
            logger.info(
                "no relevant events found",
                executed_at=executed_at.format_iso(unit="second", tz="never"),
            )
            return

        for event, reason in relevant_events:
            if notified_events.contains(event):
                logger.info(
                    "event already notified",
                    event_id=event.id,
                    event_type=event.event_type,
                    locality=event.road_summary.locality,
                )
                continue

            await notify_home_assistant(ha_client=ha_client, event=event)
            notified_events.append_event(event=event, reason=reason)

            await asyncio.sleep(3)  # delay notifications for apple timeout


if __name__ == "__main__":
    cfg = config.Config.from_env()

    asyncio.run(main(cfg=cfg))
