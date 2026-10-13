from pydantic_settings import BaseSettings, SettingsConfigDict

from status_bot.config import BotConfig


def test_encryption_key_defaults_to_empty():
    assert BotConfig().encryption_key == ""


def test_encryption_key_maps_from_environment(monkeypatch):
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

        bot: BotConfig = BotConfig()

    monkeypatch.setenv("BOT__ENCRYPTION_KEY", "env-key")
    assert Settings(_env_file=None).bot.encryption_key == "env-key"
