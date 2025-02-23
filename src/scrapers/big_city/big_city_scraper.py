import logging
import time
from datetime import datetime as dt

from selenium.webdriver.common.by import By

from src import config

logger = logging.getLogger(__name__)


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
    return {
        "organization": "Big City",
        "event_id": url.split("/")[4].split("?")[0],
        "location": location,
        "start_time": start_datetime,
        "end_time": end_datetime,
        "level": level,
        "status": status,
        "price": price,
        "url": url
    }


def get_registration_datetime(driver, url: str) -> dt:
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
    except Exception as e:
        logger.exception(f"Exception raised when collecting the registration datetime on url {url}: {e}")
        reg_datetime = None
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return reg_datetime


def get_events(driver, url: str) -> list[dict]:
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
    return events


def remove_full_events(events: list) -> list:
    i = 0
    while i < len(events):
        if events[i]["status"] == "Filled":
            events.pop(i)
        else:
            i += 1
    return events


def remove_seen_events(new_events: list, existing_event_ids: list):
    i = 0
    while i < len(new_events):
        if new_events[i]["event_id"] in existing_event_ids:
            new_events.pop(i)
        else:
            i += 1
    return new_events


def keep_advanced_events(new_events: list):
    i = 0
    while i < len(new_events):
        if new_events[i]["level"] != "Advanced":
            new_events.pop(i)
        else:
            i += 1
    return new_events
