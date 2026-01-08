import logging
import re
from datetime import datetime as dt
from urllib.parse import urljoin

import pandas as pd

from src import config
from src.scrapers.big_city import big_city_config as bc_config

logger = logging.getLogger(bc_config.LOGGER_NAME)


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
    if "Waitlist" in event_text:
        status = "Waitlist"
    elif "Filled" in event_text:
        status = "Filled"
    elif "Limited Spot" in event_text:
        status = "Available"
    
    text_normalized = re.sub(r'\s+', ' ', text_after_datetime)
    venue_pattern = r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:[A-Z]{1,3}(?:\s+[A-Z]{1,3})+\s*(?:\+\s*\d+|Join|Register)|Join|Register|\+\s*\d+)'
    venue_match = re.search(venue_pattern, text_normalized)
    if venue_match:
        location = venue_match.group(1).strip()
    else:
        fallback_pattern = r'(?:all\s+spot\s+filled|going,?\s+all\s+spot\s+filled)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)'
        fallback_match = re.search(fallback_pattern, text_normalized, re.IGNORECASE)
        location = fallback_match.group(1).strip() if fallback_match else "Unknown"
    location = re.sub(r'\s+[A-Z]{1,3}(\s+[A-Z]{1,3})*\s*$', '', location).strip()
    
    return {
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


async def get_registration_datetime(page, url: str) -> dt:
    logger.debug(f"Getting registration date on url: {url}...")
    context = page.context
    new_page = await context.new_page()
    try:
        await new_page.goto(url)
        await new_page.wait_for_load_state("networkidle")
        reg_element = new_page.locator("xpath=//span[contains(text(), 'Registration starts')]")
        reg_text = await reg_element.inner_text()
        reg_datetime = (
            dt
            .strptime(reg_text, "Registration starts %b %d %I:%M %p")
            .replace(year=dt.now().year)
        )
        if reg_datetime.date() < dt.now().date():
            reg_datetime = reg_datetime.replace(year=reg_datetime.year + 1)
        logger.debug(f"Found registration date: {reg_datetime}")
    except Exception as e:
        logger.exception(f"Exception raised when collecting the registration datetime on url {url}: {e}")
        reg_datetime = None
    finally:
        await new_page.close()
    return reg_datetime


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
    for event_info in events:
        if event_info["status"] == "Upcoming":
            event_info["registration_date"] = await get_registration_datetime(page, event_info["url"])
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
            if not (status == "Available" and existing_status in ["Filled", "Waitlist"]):
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
    logger.info("Keeping only open events (excluding filled and waitlist)...")
    num_total_events = len(events)
    i = 0
    while i < len(events):
        status = events[i]["status"]
        if status in ["Filled", "Waitlist"]:
            logger.debug(f"Event ID {events.pop(i)['event_id']} removed (status: {status}).")
        else:
            i += 1
    logger.info(f"{num_total_events - len(events)} of {num_total_events} removed. {len(events)} remaining.")
    return events
