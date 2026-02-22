import json
import logging
import urllib.request
from datetime import datetime as dt, timezone
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

import pandas as pd

from src.scrapers.big_city import big_city_config as bc_config

logger = logging.getLogger(bc_config.LOGGER_NAME)


def fetch_events_from_api() -> list[dict]:
    url = f"{bc_config.API_EVENTS_URL}?{urlencode(bc_config.API_EVENTS_PARAMS)}"
    logger.info(f"Fetching events from API: {url}")
    req = urllib.request.Request(url, headers=bc_config.API_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if body.get("response") != 200:
        raise RuntimeError(f"API returned status {body.get('response')}: {body.get('message')}")
    return body["result"]["data"]


def parse_event(api_event: dict) -> dict:
    alias_id = api_event["aliasID"]
    event_id = alias_id.rsplit("-", 1)[-1]
    event_url = urljoin(bc_config.BASE_URL, f"/posts/{alias_id}")

    tz = ZoneInfo(api_event.get("timeZone", "America/New_York"))
    start = dt.fromisoformat(api_event["start"].replace("Z", "+00:00")).astimezone(tz)
    end = dt.fromisoformat(api_event["end"].replace("Z", "+00:00")).astimezone(tz)

    place = api_event.get("place") or {}
    location = place.get("title", "Unknown")

    level_data = (api_event.get("data") or {}).get("level")
    level = level_data["title"] if level_data else None

    tickets = api_event.get("ticketsSummary", [])
    public_tickets = [t for t in tickets if t.get("ruleID") is None]
    price = public_tickets[0].get("price") if public_tickets else None
    if price is None and tickets:
        price = tickets[0].get("price")

    status = _determine_status(api_event, tickets, public_tickets)

    return {
        "organization": bc_config.ORG_DISPLAY_NAME,
        "event_id": event_id,
        "location": location,
        "start_time": start.replace(tzinfo=None),
        "end_time": end.replace(tzinfo=None),
        "level": level,
        "status": status,
        "price": str(price) if price is not None else None,
        "url": event_url,
        "date_found": dt.now(),
    }


def _determine_status(api_event: dict, tickets: list[dict], public_tickets: list[dict]) -> str:
    max_attendees = api_event.get("maxAttendees") or 0
    registered = api_event.get("registeredAttendees") or 0
    waitlist_count = api_event.get("waitlistUserCount") or 0

    if max_attendees and registered >= max_attendees:
        if waitlist_count > 0:
            return "Waitlist"
        return "Filled"

    now = dt.now(timezone.utc)
    if public_tickets:
        all_public_future = all(
            dt.fromisoformat(t["salesStart"].replace("Z", "+00:00")) > now
            for t in public_tickets
            if t.get("salesStart")
        )
        if all_public_future:
            member_tickets = [t for t in tickets if t.get("ruleID") is not None]
            any_member_on_sale = any(
                dt.fromisoformat(t["salesStart"].replace("Z", "+00:00")) <= now
                for t in member_tickets
                if t.get("salesStart")
            )
            if any_member_on_sale:
                return bc_config.MEMBERS_ONLY_STATUS
            return "Upcoming"
    elif tickets:
        all_future = all(
            dt.fromisoformat(t["salesStart"].replace("Z", "+00:00")) > now
            for t in tickets
            if t.get("salesStart")
        )
        if all_future:
            return "Upcoming"

    return "Available"


def get_events() -> list[dict]:
    logger.info("Getting events...")
    api_events = fetch_events_from_api()
    logger.debug(f"API returned {len(api_events)} events.")
    events = []
    for api_event in api_events:
        try:
            event = parse_event(api_event)
            events.append(event)
            logger.debug(f"Parsed event ID {event['event_id']}.")
        except Exception as e:
            logger.exception(f"Failed to parse event {api_event.get('aliasID', '?')}: {e}")
    logger.info(f"Parsed {len(events)} events.")
    return events


def remove_seen_events(new_events: list[dict], df_existing_events: pd.DataFrame):
    logger.info("Removing seen events...")
    num_total_events = len(new_events)
    i = 0
    while i < len(new_events):
        event_id = new_events[i]["event_id"]
        status = new_events[i]["status"]
        existing_events = df_existing_events[df_existing_events["event_id"] == event_id]
        if len(existing_events):
            existing_status = existing_events.iloc[-1]["status"]
            if not (status == "Available" and existing_status in ["Filled", "Waitlist", bc_config.MEMBERS_ONLY_STATUS]):
                logger.debug(f"Event ID {new_events.pop(i)['event_id']} removed.")
            else:
                i += 1
        else:
            i += 1
    logger.info(f"{num_total_events - len(new_events)} of {num_total_events} removed. {len(new_events)} remaining.")
    return new_events


def keep_advanced_events(events: list[dict]):
    logger.info("Keeping only advanced events...")
    num_total_events = len(events)
    i = 0
    while i < len(events):
        if events[i]["level"] != "A":
            logger.debug(f"Event ID {events.pop(i)['event_id']} removed.")
        else:
            i += 1
    logger.info(f"{num_total_events - len(events)} of {num_total_events} removed. {len(events)} remaining.")
    return events


def keep_open_events(events: list[dict]):
    """Keep events that are Available or Members Only (drop Filled, Waitlist, Upcoming)."""
    logger.info("Keeping only open events...")
    num_total_events = len(events)
    open_statuses = {"Available", bc_config.MEMBERS_ONLY_STATUS}
    i = 0
    while i < len(events):
        status = events[i]["status"]
        if status not in open_statuses:
            logger.debug(f"Event ID {events.pop(i)['event_id']} removed (status: {status}).")
        else:
            i += 1
    logger.info(f"{num_total_events - len(events)} of {num_total_events} removed. {len(events)} remaining.")
    return events
