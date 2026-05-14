"""Settings loaded from .env file."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    # ── Gmail OAuth ──────────────────────────────────────────────────────
    CREDENTIALS_DIR: Path = ROOT_DIR / "credentials"
    CLIENT_SECRET_FILE: Path = CREDENTIALS_DIR / "client_secret.json"
    TOKEN_FILE: Path = CREDENTIALS_DIR / "token.json"
    # gmail.modify lets us read, send, and manage labels (mark-processed)
    SCOPES: list[str] = [
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    # ── ZimKAG webapp ────────────────────────────────────────────────────
    ZIMKAG_URL: str = os.getenv("ZIMKAG_URL", "http://127.0.0.1:18000").rstrip("/")
    ZIMKAG_TIMEOUT: int = int(os.getenv("ZIMKAG_TIMEOUT", "300"))  # 5 min for big contracts
    ZIMKAG_USE_LLM: bool = os.getenv("ZIMKAG_USE_LLM", "true").lower() == "true"

    # ── Polling behaviour ────────────────────────────────────────────────
    POLL_INTERVAL_SEC: int = int(os.getenv("POLL_INTERVAL_SEC", "30"))
    MAX_MESSAGES_PER_POLL: int = int(os.getenv("MAX_MESSAGES_PER_POLL", "10"))
    MAX_ATTACHMENT_MB: int = int(os.getenv("MAX_ATTACHMENT_MB", "25"))
    LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1"))

    # ── Keyword filter ───────────────────────────────────────────────────
    # Minimum number of *distinct* construction-contract keywords found in
    # the attachment for it to be considered a contract worth analysing.
    MIN_KEYWORD_HITS: int = int(os.getenv("MIN_KEYWORD_HITS", "3"))

    # ── Labels ───────────────────────────────────────────────────────────
    LABEL_PROCESSED: str = os.getenv("LABEL_PROCESSED", "ZimKAG/Processed")
    LABEL_SKIPPED: str = os.getenv("LABEL_SKIPPED", "ZimKAG/Skipped")

    # ── Reply behaviour ──────────────────────────────────────────────────
    REPLY_TO_SENDER: bool = os.getenv("REPLY_TO_SENDER", "false").lower() == "true"
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"

    # ── Misc ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> None:
        if not cls.CLIENT_SECRET_FILE.exists():
            raise FileNotFoundError(
                f"Missing OAuth client secret at {cls.CLIENT_SECRET_FILE}.\n"
                f"See credentials/README.md for the 5-minute setup."
            )


settings = Settings()
settings.ensure_dirs()
