from pathlib import Path

DEFAULT_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 1.2
OSAKA_PREFIX = "\u5927\u962a\u5e9c"
RETENTION_DAYS = 31
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
OUTPUT_PATH = DOCS_DIR / "events.json"

X_ACCOUNTS = [
    "@TOKKOU_KANSAI",
    "@KD_56_PS",
]
