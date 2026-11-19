import pytest

from dossier.downloader.config import ConfigError, TelegramSettings, load_telegram_settings


def test_missing_api_id_names_the_key() -> None:
    with pytest.raises(ConfigError) as error:
        load_telegram_settings({"TELEGRAM_API_HASH": "hash", "TELEGRAM_PHONE": "+10000000000"})

    assert str(error.value) == "TELEGRAM_API_ID is not set in .env"


def test_empty_api_hash_names_the_key() -> None:
    with pytest.raises(ConfigError) as error:
        load_telegram_settings({"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "", "TELEGRAM_PHONE": "+10000000000"})

    assert str(error.value) == "TELEGRAM_API_HASH is not set in .env"


def test_missing_phone_names_the_key() -> None:
    with pytest.raises(ConfigError) as error:
        load_telegram_settings({"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "hash"})

    assert str(error.value) == "TELEGRAM_PHONE is not set in .env"


def test_non_numeric_api_id_is_rejected() -> None:
    with pytest.raises(ConfigError) as error:
        load_telegram_settings(
            {"TELEGRAM_API_ID": "abc", "TELEGRAM_API_HASH": "hash", "TELEGRAM_PHONE": "+10000000000"}
        )

    assert str(error.value) == "TELEGRAM_API_ID must be a number"


def test_complete_settings_load() -> None:
    settings = load_telegram_settings(
        {"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "hash", "TELEGRAM_PHONE": "+10000000000"}
    )

    assert settings == TelegramSettings(123, "hash", "+10000000000")
