import logging
import os
import datetime as dt
import asyncio

from playwright.async_api import async_playwright
import pandas as pd

from src import event_log, emailer, config
from src.scrapers.big_city import big_city_scraper as bc_scraper, big_city_config as bc_config
from src.scrapers.new_york_urban import new_york_urban_scraper as nyu_scraper, new_york_urban_config as nyu_config
from src.scrapers.volo import volo_scraper, volo_config


def create_logger(path_log: str = None, logger_name: str = None):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')

    if logger.hasHandlers():
        logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if path_log:
        os.makedirs(os.path.dirname(path_log), exist_ok=True)
        file_handler = logging.FileHandler(path_log)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


async def start_browser(headless=True, logger=None):
    if logger is None:
        logger = logging.getLogger(config.LOGGER_NAME)
    logger.info("Starting browser...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await context.new_page()
    logger.info("Browser started.")
    return playwright, browser, page


async def main_big_city(url: str, df_seen_events: pd.DataFrame = None) -> tuple[list[dict], bool]:
    use_file_logging = os.environ.get("GITHUB_ACTIONS") is None
    logger = create_logger(
        bc_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")) if use_file_logging else None,
        bc_config.LOGGER_NAME
    )
    logger.info(f"Starting {bc_config.ORG_DISPLAY_NAME} scraper on {url}...")
    df_seen_events = df_seen_events[df_seen_events["organization"] == bc_config.ORG_DISPLAY_NAME]
    playwright, browser, page = None, None, None
    try:
        playwright, browser, page = await start_browser(logger=logger)
        new_events = await bc_scraper.get_events(page, url)
        new_events = bc_scraper.keep_advanced_events(new_events)
        new_events = bc_scraper.keep_open_events(new_events)
        new_events = bc_scraper.remove_seen_events(new_events, df_seen_events)
        for event in new_events:
            logger.info(f"Found new event ID: {event['event_id']}")
        logger.info(f"{bc_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        return new_events, True
    except Exception as e:
        logger.warning(f"Execution failed.")
        logger.exception(e)
        return [], False
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def main_new_york_urban(url: str, df_seen_events: pd.DataFrame = None) -> tuple[list[dict], bool]:
    use_file_logging = os.environ.get("GITHUB_ACTIONS") is None
    logger = create_logger(
        nyu_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")) if use_file_logging else None,
        nyu_config.LOGGER_NAME
    )
    logger.info(f"Starting {nyu_config.ORG_DISPLAY_NAME} scraper on {url}...")
    playwright, browser, page = None, None, None
    try:
        playwright, browser, page = await start_browser(logger=logger)
        new_events = await nyu_scraper.get_events(page, url)
        new_events = nyu_scraper.remove_beginner_events(new_events)
        new_events = nyu_scraper.remove_full_events(new_events)
        new_events = nyu_scraper.remove_seen_events(new_events, df_seen_events)
        for event in new_events:
            logger.info(f"Found new event ID: {event['event_id']}")
        logger.info(f"{nyu_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        return new_events, True
    except Exception as e:
        logger.warning(f"Execution failed.")
        logger.exception(e)
        return [], False
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def main_volo(url: str, df_seen_events: pd.DataFrame = None) -> tuple[list[dict], bool]:
    use_file_logging = os.environ.get("GITHUB_ACTIONS") is None
    logger = create_logger(
        volo_config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")) if use_file_logging else None,
        volo_config.LOGGER_NAME
    )
    logger.info(f"Starting {volo_config.ORG_DISPLAY_NAME} scraper on {url}...")
    seen_event_ids = df_seen_events[df_seen_events["organization"] == volo_config.ORG_DISPLAY_NAME]["event_id"].to_list()
    playwright, browser, page = None, None, None
    try:
        playwright, browser, page = await start_browser(logger=logger)
        context = page.context
        account_login = await volo_scraper.login_to_account(
            context,
            volo_config.URL_ACCOUNT_LOGIN,
            volo_config.USERNAME,
            volo_config.PASSWORD
        )
        new_events = await volo_scraper.get_events(page, url, account_login, seen_event_ids)
        logger.info(f"{volo_config.ORG_DISPLAY_NAME} webscrape completed successfully. Found {len(new_events)} new events.")
        return new_events, True
    except Exception as e:
        logger.warning(f"Execution failed.")
        logger.exception(e)
        return [], False
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def main():
    use_file_logging = os.environ.get("GITHUB_ACTIONS") is None
    logger = create_logger(
        config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")) if use_file_logging else None,
        config.LOGGER_NAME
    )
    logger.info("Starting scraping process...")
    df_seen_events = event_log.read_local_events(config.FILEPATH_EVENT_LOG)    
    scraper_configs = [
        (main_big_city, bc_config.URL_QUERY, bc_config.ORGANIZATION),
        (main_new_york_urban, nyu_config.URL_QUERY, nyu_config.ORGANIZATION),
        # (main_volo, volo_config.URL_QUERY, volo_config.ORGANIZATION)
    ]
    org_keys = [org_key for _, _, org_key in scraper_configs]
    retry_counter = {org_key: 0 for org_key in org_keys}
    retry_counter = event_log.read_retry_counter(config.FILEPATH_RETRY_COUNTER, retry_counter)
    
    try:
        tasks = [asyncio.create_task(scraper_func(url, df_seen_events)) for scraper_func, url, _ in scraper_configs]
        results = await asyncio.gather(*tasks)
        event_lists = []
        for (events, success), org_key in zip(results, org_keys):
            event_lists.append(events)
            if success:
                retry_counter[org_key] = 0
            else:
                retry_counter[org_key] += 1
                logger.warning(f"{org_key} failed. Retry count: {retry_counter[org_key]}")
        
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
    finally:
        event_log.write_retry_counter(config.FILEPATH_RETRY_COUNTER, retry_counter)
    logger.info("Scraping process completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger = logging.getLogger(config.LOGGER_NAME)
        logger.warning(f"Main execution failed.")
        logger.exception(e)
        raise
