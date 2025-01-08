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
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')

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
    account_login = web_scraper.login_to_account(
        driver,
        config.URL_ACCOUNT_LOGIN,
        config.VOLO_USERNAME,
        config.VOLO_PASSWORD
    )
    event_ids = web_scraper.get_event_ids(driver, url, account_login)
    existing_event_ids = [] if not event_ids else event_log.read_event_ids(filepath)
    event_ids = list(set(event_ids) - set(existing_event_ids))
    if not event_ids:
        logger.info("No new open event IDs.")
    else:
        event_log.write_event_ids(filepath, event_ids)
        emailer.send_email(**emailer.create_email_content_events(event_ids))
    driver.quit()


if __name__ == "__main__":
    retry_counter = 0
    url = config.URL_QUERY
    while True:
        logger = create_logger(config.FILEPATH_LOG.format(date=dt.date.today().strftime("%Y-%m-%d")))
        logger.info(f"Starting the scraping process on {url}...")
        try:
            main(url, config.FILEPATH_EVENT_LOG)
            retry_counter = 0
            logger.info(f"Webscrape completed successfully. Sleeping for {config.SLEEP_TIME // 60} minute(s).")
            time.sleep(config.SLEEP_TIME)
        except Exception as e:
            retry_counter += 1
            logger.warning(f"Execution failed. Incrementing retry counter: {retry_counter}")
            logger.error(e)
            if retry_counter == config.RETRY_LIMIT:
                logger.fatal("Retry limit exceeded.")
                emailer.send_email(**emailer.create_email_content_job_failure(e))
                sys.exit(1)
            logger.info(f"Sleeping for {(config.SLEEP_TIME_RETRY / 60):.1f} minutes")
            time.sleep(config.SLEEP_TIME_RETRY)
