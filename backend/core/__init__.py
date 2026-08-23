from .config import settings
from .db_helper import DataBaseHelper

db_helper = DataBaseHelper(url=settings.database_url)
