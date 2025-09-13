import sqlitecloud
from config import DATABASE_URL


def get_connection():
    return sqlitecloud.connect(DATABASE_URL)
