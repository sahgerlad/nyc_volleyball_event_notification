import os

# Email config
SMTP_PORT = 587
EMAIL_SENDER = "volo.notification@gmail.com"
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

# Main config
FILEPATH_LOG = "log/log_{date}.txt"
FILEPATH_EVENT_LOG = "data/event_log.csv"
LOGGER_NAME = "main_logger"
SLEEP_TIME = 600
RETRY_LIMIT = 5
SLEEP_TIME_RETRY = 60

# Web scraper config
SLEEP_TIME_PAGE_LOAD = 5
SLEEP_TIME_URL_LOAD = 1
SLEEP_TIME_ELEMENT_LOAD = 1
SIGNUP_NOTICE = 2 * 24 * 60 * 60
