import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Enterprise Configuration for AtsCore Backend"""
    SECRET_KEY = os.getenv("SECRET_KEY")
    FLASK_ENV = os.getenv("FLASK_ENV")
    DEBUG = os.getenv("FLASK_DEBUG") in ("1", "true", "True")
    HOST = os.getenv("HOST")
    PORT = int(os.getenv("PORT")) if os.getenv("PORT") else None

    # PostgreSQL Connection Parameters
    PG_HOST = os.getenv("PG_HOST")
    PG_PORT = int(os.getenv("PG_PORT")) if os.getenv("PG_PORT") else None
    PG_DATABASE = os.getenv("PG_DATABASE")
    PG_USER = os.getenv("PG_USER")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    PG_POOL_MIN = int(os.getenv("PG_POOL_MIN")) if os.getenv("PG_POOL_MIN") else None
    PG_POOL_MAX = int(os.getenv("PG_POOL_MAX")) if os.getenv("PG_POOL_MAX") else None

    # DragonflyDB / Redis Wire Protocol Parameters
    DRAGONFLY_HOST = os.getenv("DRAGONFLY_HOST")
    DRAGONFLY_PORT = int(os.getenv("DRAGONFLY_PORT")) if os.getenv("DRAGONFLY_PORT") else None
    DRAGONFLY_DB = int(os.getenv("DRAGONFLY_DB")) if os.getenv("DRAGONFLY_DB") is not None else None
    DRAGONFLY_POOL_DB = int(os.getenv("DRAGONFLY_POOL_DB")) if os.getenv("DRAGONFLY_POOL_DB") is not None else None
    DRAGONFLY_TIMEOUT = float(os.getenv("DRAGONFLY_TIMEOUT")) if os.getenv("DRAGONFLY_TIMEOUT") else None

    # Column definitions (A through Z)
    COLS_AZ = [chr(ord("A") + i) for i in range(26)]

