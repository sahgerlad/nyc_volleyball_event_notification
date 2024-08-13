import logging
import os
import sys
import time

from src import (config, web_scraper, event_log, emailer)


def create_logger(path_log):
    os.makedirs(os.path.dirname(path_log), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(path_log),
            logging.StreamHandler()
        ]
    )
    return logging


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
            logger.info("No new event IDs")
    else:
        logger.info("No new event IDs")
    driver.quit()


if __name__ == "__main__":
    logger = create_logger(config.FILEPATH_LOG)
    logger.getLogger(__name__)
    retry_counter = 0
    while True:
        logger.info("Starting the scraping process...")
        try:
            main(config.URL, config.FILEPATH_EVENT_LOG)
            logger.info("Webscrape completed successfully. Sleeping for 1 hour.")
            time.sleep(3600)
        except Exception as e:
            logger.error(e)
            retry_counter += 1
            if retry_counter == config.RETRY_LIMIT:
                logger.fatal("Retry limit exceeded. Exiting program.")
                sys.exit(1)
