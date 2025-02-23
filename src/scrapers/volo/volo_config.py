import os

URL_ACCOUNT_LOGIN = "https://www.volosports.com/login"
URL_QUERY_TEST = "https://www.volosports.com/discover?cityName=New%20York%20Metro%20Area&view=SPORTS&subView=DAILY&programTypes%5B%5D=PICKUP&sportNames%5B%5D=Volleyball"
URL_QUERY = "https://www.volosports.com/discover?cityName=New%20York%20Metro%20Area&view=SPORTS&subView=DAILY&programTypes%5B%5D=PICKUP&sportNames%5B%5D=Volleyball&venueIds%5B%5D=60ad2493c1e4b9002fdbb04e&venueIds%5B%5D=60ad1c7ca5287c00919ec225&venueIds%5B%5D=64c875b059de744a3615b995&venueIds%5B%5D=60ad250fabc941002fb2f58c"

FILEPATH_LOG = "log/volo/log_{date}.txt"
LOGGER_NAME = "volo_logger"

USERNAME = os.environ.get("VOLO_USERNAME")
PASSWORD = os.environ.get("VOLO_PASSWORD")
