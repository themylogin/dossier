from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class TelegramSettings:
    api_id: int
    api_hash: str
    phone: str


def load_telegram_settings(environ: Mapping[str, str]) -> TelegramSettings:
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"):
        if not environ.get(key):
            raise ConfigError(f"{key} is not set in .env")
    if not environ["TELEGRAM_API_ID"].isdigit():
        raise ConfigError("TELEGRAM_API_ID must be a number")
    return TelegramSettings(int(environ["TELEGRAM_API_ID"]), environ["TELEGRAM_API_HASH"], environ["TELEGRAM_PHONE"])
