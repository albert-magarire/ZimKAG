"""Centralised settings loaded from environment variables / .env file."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    # ── LLM ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    GROQ_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    # ── Model ────────────────────────────────────────────────────────────
    MODEL_DIR: Path = (ROOT_DIR / os.getenv("MODEL_DIR", "./models/zimkag_legalbert_5class")).resolve()
    ALLOW_NO_MODEL: bool = os.getenv("ALLOW_NO_MODEL", "0") == "1"

    # ── Server ───────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ── Paths ────────────────────────────────────────────────────────────
    FRONTEND_DIR: Path = ROOT_DIR / "frontend"
    REPORTS_DIR: Path = ROOT_DIR / "reports_cache"

    # ── Inference defaults ───────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 25
    MAX_CLAUSES: int = 1000  # safety cap per document
    MIN_CLAUSE_CHARS: int = 20

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
