import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
LIVE = os.getenv("SALES_MODE") == "live"
