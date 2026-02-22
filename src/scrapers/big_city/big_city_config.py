BASE_URL = "https://app.bigcityvolleyball.com"
URL_QUERY = "https://app.bigcityvolleyball.com/big-city-volleyball/tab/open-play"

API_BASE_URL = "https://osapi.opensports.ca"
API_EVENTS_URL = f"{API_BASE_URL}/groups/layouts/tabs/listOne"
API_EVENTS_PARAMS = {
    "groupAliasID": "big-city-volleyball",
    "key": "open-play",
    "limit": "1000",
}
API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "app-id": "8058eec7-a6e7-4f85-9277-2f248c16e6f5",
    "buildnumber": "202202",
    "source": "oswebsite",
    "Referer": f"{BASE_URL}/",
}

ORGANIZATION = "big_city"
ORG_DISPLAY_NAME = "Big City"
FILEPATH_LOG = f"log/{ORGANIZATION}/log_{{date}}.txt"
LOGGER_NAME = f"{ORGANIZATION}_logger"

MEMBERS_ONLY_STATUS = "Members Only"
