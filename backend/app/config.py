from dataclasses import dataclass
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

def _load_dotenv(path: Path) -> None:
    """Small .env loader to keep local setup dependency-light."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

_load_dotenv(BASE_DIR / ".env")

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "校园集体记忆 AI 传承助手")
    app_env: str = os.getenv("APP_ENV", "development")
    app_school_name: str = os.getenv("APP_SCHOOL_NAME", "示范学校（演示环境）")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'campus_memory.db').as_posix()}")
    secret_key: str = os.getenv("SECRET_KEY", "local-demo-secret-change-before-deploy")
    token_ttl_hours: int = int(os.getenv("TOKEN_TTL_HOURS", "12"))
    ai_base_url: str = os.getenv("AI_BASE_URL", "").rstrip("/")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_model: str = os.getenv("AI_MODEL", "")
    ai_embedding_model: str = os.getenv("AI_EMBEDDING_MODEL", "")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    seed_demo_data: bool = os.getenv("SEED_DEMO_DATA", "false" if os.getenv("APP_ENV", "development").lower() == "production" else "true").lower() in {"1", "true", "yes", "on"}

settings = Settings()
