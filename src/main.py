import logging
import os
import time
import datetime as dt
import asyncio

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd

from src import event_log, emailer, config
from src.scrapers.big_city import big_city_scraper as bc_scraper, big_city_config as bc_config
from src.scrapers.new_york_urban import new_york_urban_scraper as nyu_scraper, new_york_urban_config as nyu_config
from src.scrapers.volo import volo_scraper, volo_config

logger = logging.getLogger(config.LOGGER_NAME)


def create_logger(path_log: str, logger_name: str = None):
    os.makedirs(os.path.dirname(path_log), exist_ok=True)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler(path_log)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def start_browser(headless=True, logger=logger):
    logger.info("Starting browser...")
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    logger.info("Browser started.")
    return driver


async def main_big_city(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
    def big_city(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
        logger = create_logger(
            bc_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")),
            bc_config.LOGGER_NAME
        )
        logger.info(f"Starting {bc_config.ORG_DISPLAY_NAME} scraper on {url}...")
        df_seen_events = df_seen_events[df_seen_events["organization"] == bc_config.ORG_DISPLAY_NAME]
        driver = start_browser(logger=logger)
        try:
            new_events = bc_scraper.get_events(driver, url)
            retry_counter[bc_config.ORGANIZATION] = 0
            new_events = bc_scraper.keep_advanced_events(new_events)
            new_events = bc_scraper.remove_seen_events(new_events, df_seen_events)
            for event in new_events:
                logger.info(f"Found new event ID: {event['event_id']}")
            logger.info(f"{bc_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        except Exception as e:
            retry_counter[bc_config.ORGANIZATION] += 1
            logger.warning(f"Execution failed. Incrementing retry counter: {retry_counter[bc_config.ORGANIZATION]}")
            logger.exception(e)
            new_events = []
        finally:
            driver.quit()
        return new_events
    return await asyncio.to_thread(big_city, url, df_seen_events)


async def main_new_york_urban(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
    def new_york_urban(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
        logger = create_logger(
            nyu_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")),
            nyu_config.LOGGER_NAME
        )
        logger.info(f"Starting {nyu_config.ORG_DISPLAY_NAME} scraper on {url}...")
        seen_event_ids = df_seen_events[df_seen_events["organization"] == nyu_config.ORG_DISPLAY_NAME]["event_id"].to_list()
        driver = start_browser(logger=logger)
        try:
            new_events = nyu_scraper.get_events(driver, url)
            retry_counter[nyu_config.ORGANIZATION] = 0
            new_events = nyu_scraper.remove_beginner_events(new_events)
            new_events = nyu_scraper.remove_full_events(new_events)
            new_events = nyu_scraper.remove_seen_events(new_events, seen_event_ids)
            for event in new_events:
                logger.info(f"Found new event ID: {event['event_id']}")
            logger.info(f"{nyu_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        except Exception as e:
            retry_counter[nyu_config.ORGANIZATION] += 1
            logger.warning(f"Execution failed. Incrementing retry counter: {retry_counter[nyu_config.ORGANIZATION]}")
            logger.exception(e)
            new_events = []
        finally:
            driver.quit()
        return new_events
    return await asyncio.to_thread(new_york_urban, url, df_seen_events)


async def main_volo(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
    def volo(url: str, df_seen_events: pd.DataFrame = None) -> list[dict]:
        logger = create_logger(
            volo_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")),
            volo_config.LOGGER_NAME
        )
        logger.info(f"Starting {volo_config.ORG_DISPLAY_NAME} scraper on {url}...")
        seen_event_ids = df_seen_events[df_seen_events["organization"] == volo_config.ORG_DISPLAY_NAME]["event_id"].to_list()
        driver = start_browser(logger=logger)
        try:
            account_login = volo_scraper.login_to_account(
                driver,
                volo_config.URL_ACCOUNT_LOGIN,
                volo_config.USERNAME,
                volo_config.PASSWORD
            )
            new_events = volo_scraper.get_events(driver, url, account_login, seen_event_ids)
            retry_counter[volo_config.ORGANIZATION] = 0
            logger.info(f"{volo_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        except Exception as e:
            retry_counter[volo_config.ORGANIZATION] += 1
            logger.warning(f"Execution failed. Incrementing retry counter: {retry_counter[volo_config.ORGANIZATION]}")
            logger.exception(e)
            new_events = []
        finally:
            driver.quit()
        return new_events
    return await asyncio.to_thread(volo, url, df_seen_events)


async def main():
    logger = create_logger(config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")), config.LOGGER_NAME)
    logger.info("Starting scraping process...")
    df_seen_events = event_log.read_local_events(config.FILEPATH_EVENT_LOG)
    tasks = [
        asyncio.create_task(main_big_city(bc_config.URL_QUERY, df_seen_events)),
        asyncio.create_task(main_new_york_urban(nyu_config.URL_QUERY, df_seen_events)),
        asyncio.create_task(main_volo(volo_config.URL_QUERY, df_seen_events))
    ]
    event_lists = await asyncio.gather(*tasks)
    num_events_found = sum(len(event_list) for event_list in event_lists)
    logger.info(f"Scraping complete. Found {num_events_found} new events.")
    if num_events_found or any([config.RETRY_LIMIT == retries for retries in retry_counter.values()]):
        emailer.send_email(**emailer.create_email_content_events(event_lists, retry_counter))
    if num_events_found:
        new_events = []
        [new_events.extend(event_list) for event_list in event_lists]
        df_new_events = pd.DataFrame(new_events)
        df_events = (
            event_log
            .concat_dfs(df_seen_events, df_new_events)
            .drop_duplicates(subset=["event_id"], keep="last")
        )
        df_events = df_events[df_events["start_time"] > dt.datetime.now()]
        event_log.write_events(config.FILEPATH_EVENT_LOG, df_events)
    logger.info(f"Sleeping for {(config.SLEEP_TIME / 60):.1f} minutes")
    time.sleep(config.SLEEP_TIME)


if __name__ == "__main__":
    retry_counter = {bc_config.ORGANIZATION: 0, nyu_config.ORGANIZATION: 0, volo_config.ORGANIZATION: 0}
    while True:
        asyncio.run(main())
