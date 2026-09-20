import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env once from the backend directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")

class Settings:
    """
    Centralized, validated configuration settings for the Job Agent application.
    """
    BASE_DIR: Path = _BACKEND_DIR
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-change-me")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    SCRAPINGBEE_API_KEY: str = os.getenv("SCRAPINGBEE_API_KEY", "")
    PORT: int = int(os.getenv("PORT", "5050"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    TAILORED_RESUMES_DIR: Path = _BACKEND_DIR / "tailored_resumes"
    FRONTEND_DIST: Path = _BACKEND_DIR.parent / "frontend" / "dist"

    # OAuth 2.0 Credentials & Redirection
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("CLIENT_SECRET", "")
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    OAUTH_REDIRECT_BASE_URL: str = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:5050")

    @classmethod
    def validate(cls) -> None:
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is missing or empty!")
        cls.TAILORED_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.validate()
