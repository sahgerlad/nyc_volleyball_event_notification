import logging
import time
from datetime import datetime as dt

import pandas as pd
from selenium.webdriver.common.by import By

from src import config
from src.scrapers.big_city import big_city_config as bc_config

logger = logging.getLogger(bc_config.LOGGER_NAME)


def load_query_results_page(driver, url: str) -> None:
    logger.debug(f"Loading Big City query page: {url}...")
    driver.get(url)
    time.sleep(config.SLEEP_TIME_PAGE_LOAD)
    iframe = driver.find_element(By.TAG_NAME, "iframe")
    driver.switch_to.frame(iframe)
    load_more_button = driver.find_elements(By.XPATH, "//span[text()='Load More']")
    while load_more_button:
        load_more_button[0].click()
        time.sleep(config.SLEEP_TIME_URL_LOAD)
        load_more_button = driver.find_elements(By.XPATH, "//span[text()='Load More']")
    logger.debug(f"Big City query page loaded.")


def get_event_info(event_element) -> dict:
    url = event_element.find_element(*(By.CSS_SELECTOR, "a")).get_attribute("href")
    event_id = url.split("/")[4].split("?")[0]
    event_details = event_element.text.split("\n")
    status = "Available"
    if event_details[0] in ["Filled", "Upcoming"]:
        status = event_details.pop(0)
    if len(event_details[0]) < 3:
        event_details.pop(0)
    level = event_details.pop(0).split(" ")[0]
    event_times = event_details.pop(0).split(" - ")
    start_datetime = dt.strptime(event_times[0], "%b %d %I:%M %p").replace(year=dt.now().year)
    if start_datetime < dt.now():
        start_datetime = start_datetime.replace(start_datetime.year + 1)
    if len(event_times[1].split(" ")) > 2:
        event_times[1] = " ".join(event_times[1].split(" ")[:2])
    end_datetime = dt.strptime(event_times[1], "%I:%M %p")
    end_datetime = \
        dt(start_datetime.year, start_datetime.month, start_datetime.day, end_datetime.hour, end_datetime.minute)
    location = event_details.pop(0)
    price = None
    if event_details:
        price = event_details.pop(0)
    logger.debug(f"Retrieved event ID {event_id}.")
    return {
        "organization": "Big City",
        "event_id": event_id,
        "location": location,
        "start_time": start_datetime,
        "end_time": end_datetime,
        "level": level,
        "status": status,
        "price": price,
        "url": url
    }


def get_registration_datetime(driver, url: str) -> dt:
    logger.debug(f"Getting registration date on url: {url}...")
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    try:
        driver.get(url)
        time.sleep(config.SLEEP_TIME_PAGE_LOAD)
        reg_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Registration starts')]")
        reg_datetime = (
            dt
            .strptime(reg_element.text, "Registration starts %b %d %I:%M %p")
            .replace(year=dt.now().year)
        )
        if reg_datetime < dt.now():
            reg_datetime = reg_datetime.replace(reg_datetime.year + 1)
        logger.debug(f"Found registration date: {reg_datetime}")
    except Exception as e:
        logger.exception(f"Exception raised when collecting the registration datetime on url {url}: {e}")
        reg_datetime = None
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return reg_datetime


def get_events(driver, url: str) -> list[dict]:
    logger.info(f"Getting events...")
    load_query_results_page(driver, url)
    events = []
    event_elements = (
        driver
        .find_element(By.CSS_SELECTOR, '[class*="Games_cardsContainer"]')
        .find_elements(By.XPATH, "./*")
    )
    for i, event_element in enumerate(event_elements):
        try:
            events.append(get_event_info(event_element))
        except Exception as e:
            logger.exception(f"Exception raised when collecting event info for index {i}: {e}")
    for event_info in events:
        if event_info["status"] == "Upcoming":
            event_info["registration_date"] = get_registration_datetime(driver, event_info["url"])
    logger.info("Retrieved all event info.")
    return events


def remove_seen_events(new_events: list[dict], df_existing_events: pd.DataFrame):
    logger.info("Removing seen events...")
    num_total_events = len(new_events)
    i = 0
    while i < len(new_events):
        event_id = new_events[i]["event_id"]
        status = new_events[i]["status"]
        if len(
            df_existing_events[
                (df_existing_events["event_id"] == event_id) &
                ((df_existing_events["status"] == status) | (df_existing_events["status"].isin(["Available", "Filled"])))
            ]
        ):
            logger.debug(f"Event ID {new_events.pop(i)['event_id']} removed.")
        else:
            i += 1
    logger.info(f"{num_total_events - len(new_events)} of {num_total_events} removed. {len(new_events)} remaining.")
    return new_events


def keep_advanced_events(events: list[dict]):
    logger.info("Keeping only advanced events...")
    num_total_events = len(events)
    i = 0
    while i < len(events):
        if events[i]["level"] != "Advanced":
            logger.debug(f"Event ID {events.pop(i)['event_id']} removed.")
        else:
            i += 1
    logger.info(f"{num_total_events - len(events)} of {num_total_events} removed. {len(events)} remaining.")
    return events


