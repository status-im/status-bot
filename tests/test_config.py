from pydantic_settings import BaseSettings, SettingsConfigDict

from status_bot.config import BotConfig


def test_bot_hash_pepper_defaults_to_empty():
    assert BotConfig().bot_hash_pepper == ""


def test_bot_hash_pepper_maps_from_environment(monkeypatch):
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

        bot: BotConfig = BotConfig()

    monkeypatch.setenv("BOT__BOT_HASH_PEPPER", "env-pepper")
    assert Settings(_env_file=None).bot.bot_hash_pepper == "env-pepper"