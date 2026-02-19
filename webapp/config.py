import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    APP_TITLE = "CIA World Factbook Archive"
    DB_PATH = os.getenv("DB_PATH", str(_PROJECT_ROOT / "data" / "factbook.db"))
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO = "MilkMp/CIA-World-Factbooks-Archive-1990-2025"
    MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


settings = Settings()
