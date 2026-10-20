from pydantic_settings import BaseSettings, SettingsConfigDict

from status_bot.config import BotConfig, ModulesConfig


def test_encryption_key_defaults_to_empty():
    assert BotConfig().encryption_key == ""


def test_encryption_key_maps_from_environment(monkeypatch):
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

        bot: BotConfig = BotConfig()

    monkeypatch.setenv("BOT__ENCRYPTION_KEY", "env-key")
    assert Settings(_env_file=None).bot.encryption_key == "env-key"


def test_config_directory_defaults_to_none():
    assert ModulesConfig().config_directory is None


def test_config_directory_maps_from_environment(monkeypatch):
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

        modules: ModulesConfig = ModulesConfig()

    monkeypatch.setenv("MODULES__CONFIG_DIRECTORY", "/etc/status-bot/module-configs")
    assert Settings(_env_file=None).modules.config_directory == "/etc/status-bot/module-configs"
