import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Enterprise Configuration for AtsCore Backend"""
    SECRET_KEY = os.getenv("SECRET_KEY", "ats_enterprise_secret_key_secure_2026")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    # PostgreSQL Connection Parameters
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "ats_recovery_db")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "ats_enterprise_pg_pass_2026")
    PG_POOL_MIN = int(os.getenv("PG_POOL_MIN", "4"))
    PG_POOL_MAX = int(os.getenv("PG_POOL_MAX", "32"))

    # DragonflyDB / Redis Wire Protocol Parameters
    DRAGONFLY_HOST = os.getenv("DRAGONFLY_HOST", "127.0.0.1")
    DRAGONFLY_PORT = int(os.getenv("DRAGONFLY_PORT", "6379"))
    DRAGONFLY_DB = int(os.getenv("DRAGONFLY_DB", "0"))
    DRAGONFLY_POOL_DB = int(os.getenv("DRAGONFLY_POOL_DB", "1"))
    DRAGONFLY_TIMEOUT = float(os.getenv("DRAGONFLY_TIMEOUT", "0.5"))

    # Source SQLite database path for migration
    SQLITE_SOURCE_PATH = os.getenv(
        "SQLITE_SOURCE_PATH",
        r"E:\master_sheet\Fast_Excel_Sheet.db"
    )

    # Column definitions (A through Z)
    COLS_AZ = [chr(ord("A") + i) for i in range(26)]

