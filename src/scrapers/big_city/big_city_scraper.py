import json
import logging
import re
import urllib.request
from datetime import datetime as dt, timezone
from urllib.parse import urljoin

import pandas as pd

from src import config
from src.scrapers.big_city import big_city_config as bc_config

logger = logging.getLogger(bc_config.LOGGER_NAME)


def check_members_only(event_url: str) -> bool:
    """Fetch an event page via HTTP and check if general-public tickets are on sale yet.

    The page embeds __NEXT_DATA__ with a ticketsSummary. Tickets restricted to
    members have a non-null ruleID. If every ticket without a ruleID has a
    salesStart in the future, the event is still in the members-only window.
    """
    try:
        req = urllib.request.Request(event_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to fetch event page {event_url}: {e}")
        return False

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not match:
        logger.warning(f"No __NEXT_DATA__ found for {event_url}")
        return False

    try:
        data = json.loads(match.group(1))
        post_list = data["props"]["initialState"]["postDetail"]["list"]
        if not post_list:
            return False
        tickets = post_list[0].get("ticketsSummary", [])
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse ticket data for {event_url}: {e}")
        return False

    public_tickets = [t for t in tickets if t.get("ruleID") is None]
    if not public_tickets:
        return True

    now = dt.now(timezone.utc)
    return all(
        dt.fromisoformat(t["salesStart"].replace("Z", "+00:00")) > now
        for t in public_tickets
        if t.get("salesStart")
    )


def mark_members_only_events(events: list[dict]) -> list[dict]:
    logger.info("Checking events for members-only early access...")
    for event in events:
        if check_members_only(event["url"]):
            logger.info(f"Event ID {event['event_id']} is members-only.")
            event["status"] = bc_config.MEMBERS_ONLY_STATUS
    members_only_count = sum(1 for e in events if e["status"] == bc_config.MEMBERS_ONLY_STATUS)
    logger.info(f"{members_only_count} of {len(events)} events are members-only.")
    return events


async def load_query_results_page(page, url: str):
    logger.debug(f"Loading {bc_config.ORG_DISPLAY_NAME} query page: {url}...")
    await page.goto(url)
    await page.wait_for_load_state("networkidle")
    while True:
        load_more_button = page.locator("text=Load More")
        if await load_more_button.count() == 0:
            break
        await load_more_button.first.click()
        await page.wait_for_timeout(config.SLEEP_TIME_URL_LOAD)
    logger.debug(f"{bc_config.ORG_DISPLAY_NAME} query page loaded.")
    return page


async def get_event_info(event_locator) -> dict:
    url = await event_locator.get_attribute("href")
    if url and url.startswith("/"):
        url = urljoin(bc_config.BASE_URL, url)
    slug = url.split("/")[-1].split("?")[0].rstrip("-")
    event_id = slug.rsplit("-", 1)[-1]
    event_text = await event_locator.inner_text()
    level_match = re.match(r'^(A|BB|B|All Skill Levels)\s+', event_text)
    level = level_match.group(1) if level_match else None

    datetime_pattern = r'([A-Za-z]{3})\s+([A-Za-z]{3})\s+(\d{1,2})(?:,\s+(\d{4}))?\s+(\d{1,2}:\d{2}\s+[AP]M)\s+-\s+(\d{1,2}:\d{2}\s+[AP]M)'
    datetime_match = re.search(datetime_pattern, event_text)
    if not datetime_match:
        raise ValueError(f"Could not parse date/time from event text: {event_text[:100]}")
    day_name, month, day, year, start_time, end_time = datetime_match.groups()
    if year:
        start_datetime_str = f"{month} {day}, {year} {start_time}"
        start_datetime = dt.strptime(start_datetime_str, "%b %d, %Y %I:%M %p")
    else:
        start_datetime_str = f"{month} {day} {start_time}"
        start_datetime = dt.strptime(start_datetime_str, "%b %d %I:%M %p").replace(year=dt.now().year)
        if start_datetime.date() < dt.now().date():
            start_datetime = start_datetime.replace(year=start_datetime.year + 1)
    end_datetime = dt.strptime(end_time, "%I:%M %p")
    end_datetime = dt(start_datetime.year, start_datetime.month, start_datetime.day, 
                      end_datetime.hour, end_datetime.minute)
    text_after_datetime = event_text[datetime_match.end():]
    
    price_match = re.search(r'\|\s+(\$[\d.]+)', event_text)
    price = price_match.group(1) if price_match else None
    if price_match:
        text_after_datetime = text_after_datetime.split("|", 1)[-1].strip()
    
    status = "Available"
    button = event_locator.locator("button")
    if await button.count() > 0:
        is_disabled = await button.first.is_disabled()
        if is_disabled:
            status = "Upcoming"
        elif "Waitlist" in event_text:
            status = "Waitlist"
        elif "Filled" in event_text:
            status = "Filled"
        elif "Limited Spot" in event_text:
            status = "Available"
    
    location_element = event_locator.locator(
        'span.Card_sectionPadding__H36_y[style*="font-size: 14px"][style*="margin-bottom: 10px"]'
    )
    if await location_element.count() > 0:
        location = (await location_element.first.inner_text()).strip()
    else:
        location = "Unknown"

    event_info = {
        "organization": bc_config.ORG_DISPLAY_NAME,
        "event_id": event_id,
        "location": location,
        "start_time": start_datetime,
        "end_time": end_datetime,
        "level": level,
        "status": status,
        "price": price.strip("$") if isinstance(price, str) and "$" in price else price,
        "url": url,
        "date_found": dt.now()
    }
    logger.debug(f"Event info: {event_info}")
    return event_info


async def get_events(page, url: str) -> list[dict]:
    logger.info(f"Getting events...")
    page = await load_query_results_page(page, url)
    events = []
    event_elements = page.locator('a[href*="/posts/"]')
    count = await event_elements.count()
    logger.debug(f"Found {count} event elements.")
    for i in range(count):
        try:
            event_locator = event_elements.nth(i)
            event_info = await get_event_info(event_locator)
            events.append(event_info)
            logger.debug(f"Retrieved event ID {events[-1]['event_id']}.")
        except Exception as e:
            logger.exception(f"Exception raised when collecting event info for index {i}: {e}")
    logger.info(f"Retrieved event info for {len(events)} events.")
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
    logger.info("Keeping only events with status 'Available'...")
    num_total_events = len(events)
    i = 0
    while i < len(events):
        status = events[i]["status"]
        if status != "Available":
            logger.debug(f"Event ID {events.pop(i)['event_id']} removed (status: {status}).")
        else:
            i += 1
    logger.info(f"{num_total_events - len(events)} of {num_total_events} removed. {len(events)} remaining.")
    return events
