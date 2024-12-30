import logging
import time
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


def get_event_ids(driver, url: str, account_login: bool):
    load_query_results_page(driver, url)
    logger.info(f"Getting events...")
    event_ids = []
    query_element = get_query_element(driver)
    if "No results" in query_element.text:
        return event_ids
    page_elements = get_page_elements(query_element)
    for page in range(len(page_elements)):
        _, event_elements = refresh_elements(driver, url, page, account_login)
        logger.info(f"Found {len(event_elements)} open event(s) on page {page + 1}.")
        for idx in range(len(event_elements)):
            event_elements[idx].find_elements(By.XPATH, ".//div[@dir]")[0].click()
            time.sleep(1)
            event_id = driver.current_url.split("/")[-1]
            event_ids.append(event_id)
            _, event_elements = refresh_elements(driver, url, page, account_login)
            logger.info(f"Retrieved event ID: {event_id}")
    logger.info("Retrieved all event IDs.")
    return event_ids
