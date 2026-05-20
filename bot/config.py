from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource


class BotParams(BaseModel):
    domain: str = "localhost"
    port: int = 8080
    is_secure: bool = False


class BotConfig(BaseModel):
    display_name: str = ""
    public_key: str = ""
    password: str = ""
    mnemonic_phrase: str = ""
    init_account: bool = False
    compressed_key: str = ""
    infura_token: str = ""
    coingecko_api_key: str = ""
    params: BotParams = BotParams()


class PostgresConfig(BaseModel):
    host: str = "database"
    port: int = 5432
    user: str = ""
    password: str = ""
    name: str = ""
    schema: str = "public"
    tables: dict = {}


class PrometheusConfig(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000


class FilesConfig(BaseModel):
    current_state: str = "dates.pkl"


class ModulesConfig(BaseModel):
    directories: list[str] = ["./modules", "bot/modules"]
    enabled: list[str] = []
    settings: dict = {}


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )

    sleep: int = 10
    files: FilesConfig = FilesConfig()
    bot: BotConfig = BotConfig()
    modules: ModulesConfig = ModulesConfig()
    prometheus: PrometheusConfig = PrometheusConfig()
    postgres: PostgresConfig = PostgresConfig()

    _yaml_file = "./config.yaml"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            YamlConfigSettingsSource(settings_cls, yaml_file=cls._yaml_file),
            env_settings,
            dotenv_settings,
        )
