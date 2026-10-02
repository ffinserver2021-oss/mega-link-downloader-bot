import os

class Config(object):
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    AUTH_USERS = [int(x) for x in os.environ.get("AUTH_USERS", "").split()]
    OWNER_ID = int(os.environ.get("OWNER_ID", 0))
    DOWNLOAD_LOCATION = "./DOWNLOADS"
    MEGA_EMAIL = os.environ.get("MEGA_EMAIL", "")
    MEGA_PASSWORD = os.environ.get("MEGA_PASSWORD", "")
