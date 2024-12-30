import os

# Web config
URL_ACCOUNT_LOGIN = "https://www.volosports.com/login"
URL_QUERY_TEST = "https://www.volosports.com/discover?cityName=New%20York%20Metro%20Area&view=SPORTS&subView=DAILY&programTypes%5B%5D=PICKUP&sportNames%5B%5D=Volleyball"
URL_QUERY = "https://www.volosports.com/discover?cityName=New%20York%20Metro%20Area&view=SPORTS&subView=DAILY&programTypes%5B%5D=PICKUP&sportNames%5B%5D=Volleyball&venueIds%5B%5D=60ad2493c1e4b9002fdbb04e&venueIds%5B%5D=60ad1c7ca5287c00919ec225&venueIds%5B%5D=64c875b059de744a3615b995&venueIds%5B%5D=60ad250fabc941002fb2f58c"

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "volo.notification@gmail.com"
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

# Volo account
VOLO_USERNAME = os.environ.get("VOLO_USERNAME")
VOLO_PASSWORD = os.environ.get("VOLO_PASSWORD")

# File config
FILEPATH_LOG = "log/log_{date}.txt"
FILEPATH_EVENT_LOG = "data/event_log.csv"

# Main config
SLEEP_TIME = 1800
RETRY_LIMIT = 5
SLEEP_TIME_RETRY = 60
