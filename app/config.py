from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse


DEFAULT_BOT_DESCRIPTION = (
    "Привет. Я помогаю с таро, гороскопами, рунами и небольшими мистическими ритуалами.\n"
    "Напиши /start, чтобы открыть быстрое меню."
)
DEFAULT_BOT_SHORT_DESCRIPTION = (
    "Таро, гороскопы, руны и мистические подсказки на каждый день."
)


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env without external dependencies."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    bot_username: str | None
    bot_name: str | None
    bot_description: str
    bot_short_description: str
    database_path: Path
    openai_api_key: str | None
    openai_model: str
    bot_mode: str = "auto"
    webhook_url: str | None = None
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path: str = "/telegram/webhook"
    webhook_secret_token: str | None = None
    subscription_poll_interval: int = 30
    polling_timeout: int = 30
    request_timeout: int = 40

    @property
    def run_mode(self) -> str:
        if self.bot_mode == "auto":
            return "webhook" if self.webhook_url else "polling"
        return self.bot_mode

    @classmethod
    def from_env(cls, project_root: Path) -> "Settings":
        load_env_file(project_root / ".env")

        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не найден BOT_TOKEN. Добавь его в переменные окружения или в файл .env."
            )

        raw_username = os.getenv("BOT_USERNAME", "").strip()
        bot_username = raw_username or None
        if bot_username and not bot_username.startswith("@"):
            bot_username = f"@{bot_username}"

        bot_name = os.getenv("BOT_NAME", "").strip() or None
        bot_description = (
            os.getenv("BOT_DESCRIPTION", "").strip() or DEFAULT_BOT_DESCRIPTION
        )
        bot_short_description = (
            os.getenv("BOT_SHORT_DESCRIPTION", "").strip()
            or DEFAULT_BOT_SHORT_DESCRIPTION
        )

        database_path = Path(
            os.getenv("DATABASE_PATH", "bot_data.sqlite3").strip() or "bot_data.sqlite3"
        )
        if not database_path.is_absolute():
            database_path = project_root / database_path

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
        bot_mode = (os.getenv("BOT_MODE", "auto").strip().casefold() or "auto")
        if bot_mode not in {"auto", "polling", "webhook"}:
            raise RuntimeError(
                "BOT_MODE должен быть одним из значений: auto, polling, webhook."
            )

        webhook_url = os.getenv("WEBHOOK_URL", "").strip() or None
        webhook_host = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip() or "0.0.0.0"
        webhook_port = int(os.getenv("WEBHOOK_PORT", "8080"))
        webhook_secret_token = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip() or None

        raw_webhook_path = os.getenv("WEBHOOK_PATH", "").strip()
        if raw_webhook_path:
            webhook_path = cls._normalize_webhook_path(raw_webhook_path)
        elif webhook_url:
            webhook_path = cls._normalize_webhook_path(urlparse(webhook_url).path)
        else:
            webhook_path = "/telegram/webhook"

        if webhook_url:
            parsed_webhook_url = urlparse(webhook_url)
            if parsed_webhook_url.scheme != "https" or not parsed_webhook_url.netloc:
                raise RuntimeError(
                    "WEBHOOK_URL должен быть полным https-адресом, например https://bot.example.com/telegram/webhook."
                )

        subscription_poll_interval = int(os.getenv("SUBSCRIPTION_POLL_INTERVAL", "30"))
        polling_timeout = int(os.getenv("POLLING_TIMEOUT", "30"))
        request_timeout = int(os.getenv("REQUEST_TIMEOUT", "40"))
        return cls(
            bot_token=token,
            bot_username=bot_username,
            bot_name=bot_name,
            bot_description=bot_description,
            bot_short_description=bot_short_description,
            database_path=database_path,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            bot_mode=bot_mode,
            webhook_url=webhook_url,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
            webhook_path=webhook_path,
            webhook_secret_token=webhook_secret_token,
            subscription_poll_interval=subscription_poll_interval,
            polling_timeout=polling_timeout,
            request_timeout=request_timeout,
        )

    @staticmethod
    def _normalize_webhook_path(raw_path: str) -> str:
        normalized = raw_path.strip() or "/telegram/webhook"
        if normalized.startswith("http://") or normalized.startswith("https://"):
            normalized = urlparse(normalized).path
        normalized = f"/{normalized.lstrip('/')}"
        return normalized.rstrip("/") or "/"
