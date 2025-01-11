import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
        time.sleep(5)
        driver.find_element(By.ID, "credential").send_keys(volo_account)
        password_element = driver.find_element(By.ID, "password")
        password_element.send_keys(volo_password)
        password_element.send_keys(Keys.RETURN)
        time.sleep(1)
        if driver.current_url == url:
            logger.error(f"Login attempt to Volo account unsuccessful.")
        else:
            account_login = True
            logger.info(f"Login to Volo account successful.")
    except Exception as e:
        logger.warning(f"Error when attempting to log into the Volo account: {e}")
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return account_login


def load_query_results_page(driver, url):
    logger.debug(f"Loading Volo query page: {url}...")
    driver.get(url)
    time.sleep(5)  # Add delay for page to fully load
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
    get_page_elements(query_element)[page].click()
    time.sleep(1)
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


def parse_event_datetime(date_string, time_range):
    # Parse date
    date_object = datetime.strptime(date_string, "%a, %B %d")
    current_date = datetime.now()
    date_object = date_object.replace(year=current_date.year)
    if date_object < current_date:
        date_object = date_object.replace(year=current_date.year + 1)

    # Parse time
    start_time, end_time = time_range.split(" - ")
    start_datetime = datetime.strptime(start_time, "%I:%M%p")
    end_datetime = datetime.strptime(end_time, "%I:%M%p")

    start_datetime = date_object.replace(hour=start_datetime.hour, minute=start_datetime.minute)
    end_datetime = date_object.replace(hour=end_datetime.hour, minute=end_datetime.minute)
    return start_datetime, end_datetime


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


def get_events(driver, url: str, account_login: bool):
    load_query_results_page(driver, url)
    logger.info(f"Getting events...")
    events = []
    query_element = get_query_element(driver)
    if "No results" in query_element.text:
        return events
    page_elements = get_page_elements(query_element)
    for page in range(len(page_elements)):
        _, event_elements = refresh_elements(driver, url, page, account_login)
        logger.info(f"Found {len(event_elements)} open event(s) on page {page + 1}.")
        for idx in range(len(event_elements)):
            event_elements[idx].find_elements(By.XPATH, ".//div[@dir]")[0].click()
            time.sleep(5)
            event_info = get_event_info(driver)
            events.append(event_info)
            _, event_elements = refresh_elements(driver, url, page, account_login)
            logger.info(f"Retrieved event ID: {event_info['event_id']}")
    logger.info("Retrieved all event IDs.")
    return events
