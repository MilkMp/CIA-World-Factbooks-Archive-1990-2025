"""
Startup script for containerized deployment.

On first boot, copies the bundled SQLite database to the persistent volume.
Then starts the FastAPI app via Uvicorn.
"""

import os
import shutil
import subprocess
import sys

DB_VOLUME = os.environ.get("DB_PATH", "/data/factbook.db")
DB_BUNDLED = "/app/data/factbook.db"


def main():
    # Always sync bundled DB to persistent volume (read-only archive, no user data)
    if os.path.exists(DB_BUNDLED):
        bundled_size = os.path.getsize(DB_BUNDLED)
        volume_size = os.path.getsize(DB_VOLUME) if os.path.exists(DB_VOLUME) else 0
        if bundled_size != volume_size:
            os.makedirs(os.path.dirname(DB_VOLUME), exist_ok=True)
            print(f"Updating database on volume ({volume_size/1024/1024:.1f} -> {bundled_size/1024/1024:.1f} MB)...")
            shutil.copy2(DB_BUNDLED, DB_VOLUME)
            print("Database updated.")

    if not os.path.exists(DB_VOLUME):
        print(f"ERROR: Database not found at {DB_VOLUME}", file=sys.stderr)
        sys.exit(1)

    port = os.environ.get("PORT", "8080")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "webapp.main:app",
        "--host", "0.0.0.0",
        "--port", port,
    ])


if __name__ == "__main__":
    main()
