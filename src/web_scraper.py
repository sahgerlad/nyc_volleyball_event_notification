import logging
import time
from datetime import datetime as dt

import selenium.common
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from src import config

logger = logging.getLogger(__name__)


def start_browser(headless=True):
    logger.info("Starting browser...")
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    logger.info("Browser started.")
    return driver


def login_to_account(driver, url, volo_account, volo_password):
    logger.info(f"Logging into Volo account with username {volo_account}: {url}...")
    account_login = False
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    try:
        driver.get(url)
        time.sleep(config.SLEEP_TIME_PAGE_LOAD)
        driver.find_element(By.ID, "credential").send_keys(volo_account)
        password_element = driver.find_element(By.ID, "password")
        password_element.send_keys(volo_password)
        password_element.send_keys(Keys.RETURN)
        time.sleep(config.SLEEP_TIME_URL_LOAD)
        if driver.current_url == url:
            logger.error(f"Login attempt to Volo account unsuccessful.")
        else:
            account_login = True
            logger.info(f"Login to Volo account successful.")
    except Exception as e:
        logger.exception(f"Error when attempting to log into the Volo account: {e}")
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return account_login


def load_query_results_page(driver, url):
    logger.debug(f"Loading Volo query page: {url}...")
    driver.get(url)
    time.sleep(config.SLEEP_TIME_PAGE_LOAD)
    logger.debug(f"Volo query page loaded.")


def get_query_element(driver):
    elements = (
        driver.find_element(By.CSS_SELECTOR, "main")
        .find_elements(By.CSS_SELECTOR, "div")
    )
    for i, elem in enumerate(elements):
        if elem.text.startswith("Pickup") and ":" in elem.text:
            return elements[i - 3]
        elif elem.text.startswith("No results"):
            return elements[i]


def get_page_elements(query_element):
    page_elements = (
        query_element
        .find_elements(By.XPATH, "./*")[-1]
        .find_elements(By.XPATH, ".//div[@tabindex]")[1:-1]
    )
    return page_elements


def refresh_elements(driver, url, page, account_login):
    load_query_results_page(driver, url)
    query_element = get_query_element(driver)
    if "No results" in query_element.text:
        return None, []
    get_page_elements(query_element)[page].click()
    time.sleep(config.SLEEP_TIME_ELEMENT_LOAD)
    query_element = get_query_element(driver)
    event_elements = get_event_elements(query_element, account_login)
    return query_element, event_elements


def get_event_elements(query_element, account_login: bool):
    event_elements = query_element.find_elements(By.XPATH, "./*")
    valid_event_elements = []
    for element in event_elements:
        # Remove elements that do not contain an event
        if "Pickup" not in element.text:
            continue
        # Remove full events (need to be logged in to see event capacity)
        if account_login:
            event_capacity = element.find_elements(By.XPATH, ".//div[@dir]")[-1].text.split("/")
            try:
                if event_capacity[0] == event_capacity[1]:
                    continue
            except IndexError:
                logger.debug(
                    f"Event capacity could not be found: {element.find_elements(By.XPATH, ".//div[@dir]")[-1].text}"
                )
        valid_event_elements.append(element)
    return valid_event_elements


def parse_event_datetime(str_date, time_range):
    dt_start = dt.strptime(str_date, "%a, %B %d")
    str_start_time, str_end_time = time_range.split(" - ")
    dt_start_time = dt.strptime(str_start_time, "%I:%M%p")
    dt_current = dt.now()
    dt_start = dt_start.replace(year=dt_current.year, hour=dt_start_time.hour, minute=dt_start_time.minute)
    if dt_current > dt_start:
        dt_start = dt_start.replace(year=dt_current.year + 1)
    dt_end_time = dt.strptime(str_end_time, "%I:%M%p")
    dt_end = dt_start.replace(hour=dt_end_time.hour, minute=dt_end_time.minute)
    return dt_start, dt_end


def get_event_info(driver):
    event_id = driver.current_url.split("/")[-1]
    event_details_element = driver.find_element(By.CSS_SELECTOR, "[class^='styles_program-detail-item-container']")
    event_details = event_details_element.text.split("\n")
    start_datetime, end_datetime = parse_event_datetime(event_details[0], event_details[2])
    location = event_details[3] + ", " + event_details[1]
    level = event_details[4] if len(event_details) >= 5 else None
    return {
        "event_id": event_id,
        "location": location,
        "start_time": start_datetime,
        "end_time": end_datetime,
        "level": level
    }


def get_events(driver, url: str, account_login: bool, existing_events: list = None):
    load_query_results_page(driver, url)
    logger.info(f"Getting events...")
    events = []
    query_element = get_query_element(driver)
    if "No results" in query_element.text:
        return events
    page_elements = get_page_elements(query_element)
    page = 0
    while page < len(page_elements):
        if page == 0:
            event_elements = get_event_elements(query_element, account_login)
        else:
            _, event_elements = refresh_elements(driver, url, page, account_login)
        logger.info(f"Found {len(event_elements)} open event(s) on page {page + 1}.")
        idx = 0
        while idx < len(event_elements):
            try:
                event_elements[idx].find_elements(By.XPATH, ".//div[@dir]")[0].click()
                time.sleep(config.SLEEP_TIME_PAGE_LOAD)
                event_info = get_event_info(driver)
                if (
                    event_info["event_id"] in existing_events
                    or any(d["event_id"] == event_info["event_id"] for d in events)
                    or "You are already registered!" in driver.page_source
                ):
                    idx += 1
                    logger.info(
                        f"Found event ID {event_info['event_id']} but event ID is not new."
                    )
                    continue
                registration_confirmed = False
                if (
                    account_login
                    and (event_info["start_time"] - dt.now()).total_seconds() > config.SIGNUP_NOTICE
                    and check_free_event(driver)
                ):
                    registration_confirmed = event_registration(driver)
                event_info["registered"] = registration_confirmed
                logger.info(
                    f"Retrieved event ID {event_info['event_id']} and registration is {'not ' if not registration_confirmed else ''}confirmed."
                )
                events.append(event_info)
                if not registration_confirmed:
                    idx += 1
            except Exception as e:
                logger.exception(f"Exception encountered while collecting event index {idx} on page {page + 1}: {e}")
                idx += 1
                logger.info(f"Index incremented to {idx}")
            finally:
                _, event_elements = refresh_elements(driver, url, page, account_login)
        load_query_results_page(driver, url)
        query_element = get_query_element(driver)
        if "No results" in query_element.text:
            break
        page += 1
        page_elements = get_page_elements(query_element)
    logger.info("Retrieved all event IDs.")
    return events


def check_free_event(driver):
    page_source = driver.page_source
    free_event = False
    if "$0.00" in page_source[page_source.index("Order Total"):]:
        free_event = True
    return free_event


def event_registration(driver):
    checkbox_elements = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for element in checkbox_elements:
        element.click()
    register_element = driver.find_element(By.XPATH, "//button[contains(text(), 'Register')]")
    register_element.click()
    time.sleep(config.SLEEP_TIME_PAGE_LOAD)
    registration_confirmed = False
    try:
        driver.find_element(By.XPATH, "//*[contains(text(), 'Your spot has been confirmed!')]")
        registration_confirmed = True
    except selenium.common.NoSuchElementException:
        logger.warning("Attempted to register for event but could not identify confirmation")
    return registration_confirmed
