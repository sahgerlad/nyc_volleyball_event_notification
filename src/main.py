import logging
import os
import sys
import time
import datetime as dt

from src import (config, web_scraper, event_log, emailer)


def create_logger(path_log):
    os.makedirs(os.path.dirname(path_log), exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler(path_log)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def main(url, filepath):
    driver = web_scraper.start_browser()
    event_ids = web_scraper.get_event_ids(driver, url)
    if event_ids:
        existing_event_ids = event_log.read_event_ids(filepath)
        event_ids = list(set(event_ids) - set(existing_event_ids))
        if event_ids:
            event_log.write_event_ids(filepath, event_ids)
            emailer.send_email(event_ids)
        else:
            logger.info("No new event ID(s)")
    else:
        logger.info("No new event ID(s)")
    driver.quit()


if __name__ == "__main__":
    retry_counter = 0
    while True:
        logger = create_logger(config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")))
        logger.info("Starting the scraping process...")
        try:
            main(config.URL, config.FILEPATH_EVENT_LOG)
        except Exception as e:
            logger.error(e)
            retry_counter += 1
            if retry_counter == config.RETRY_LIMIT:
                logger.fatal("Retry limit exceeded. Exiting program.")
                sys.exit(1)
        logger.info(f"Webscrape completed successfully. Sleeping for {config.SLEEP_TIME // 60} minute(s).")
        time.sleep(config.SLEEP_TIME)
