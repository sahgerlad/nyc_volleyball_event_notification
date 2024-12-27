import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


def start_browser(headless=False):
    logger.info("Starting browser...")
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    logger.info("Browser started.")
    return driver


def get_query_element(driver, url):
    driver.get(url)
    # Add delay for page to fully load
    time.sleep(5)
    elements = (
        driver.find_element(By.CSS_SELECTOR, "main")
        .find_elements(By.CSS_SELECTOR, "div")
    )
    for i, elem in enumerate(elements):
        if elem.text.startswith("Pickup") and ":" in elem.text:
            return elements[i - 3]
        elif elem.text.startswith("No results"):
            return elements[i]


def get_event_elements(query_element):
    event_elements = query_element.find_elements(By.XPATH, "./*")
    idx = 0
    while idx != len(event_elements):
        if len(event_elements[idx].find_elements(By.CSS_SELECTOR, "div")) == 1:
            event_elements.pop(idx)
        else:
            idx += 1
    return event_elements[:-1]


def get_event_ids(driver, url: str):
    logger.info(f"Getting events from url: {url}")
    query_element = get_query_element(driver, url)
    event_elements = get_event_elements(query_element)
    logger.info(f"Found {len(event_elements)} event(s).")
    event_ids = []
    if len(event_elements):
        for idx in range(len(event_elements)):
            for element in event_elements[idx].find_elements(By.CSS_SELECTOR, "div"):
                if element.text == "Pickup":
                    element.click()
                    break
            time.sleep(1)
            event_id = driver.current_url.split("/")[-1]
            event_ids.append(event_id)
            query_element = get_query_element(driver, url)
            event_elements = get_event_elements(query_element)
            logger.info(f"Retrieved event ID: {event_id}")
        logger.info("Retrieved all event IDs.")
    return event_ids
