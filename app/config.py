from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "static"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "nurse_roster.sqlite3"

APP_TITLE = "護理排班系統"
DEFAULT_PERIOD_FROM = "2026-01-01"
DEFAULT_PERIOD_TO = "2026-01-14"

for folder in (DATA_DIR, STATIC_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)
