from typing import Optional, ClassVar, Literal
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource


class LoggingConfig(BaseModel):
    format: Literal["human", "json"] = "human"
    level: Literal["debug", "info", "warning", "error"] = "info"
    uvicorn_access: bool = False


class BackendConfig(BaseModel):
    domain: str = "localhost"
    backend_port: int = 8080
    is_secure: bool = False

class BotConfig(BaseModel):
    name: str = ""
    chat_key: str = ""
    password: str = ""
    mnemonic_phrase: Optional[str] = None
    infura_token: Optional[str] = None
    alchemy_token: Optional[str] = None
    coingecko_api_key: Optional[str] = ""
    bot_hash_pepper: str = ""

class DatabaseConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    type: str = "postgres"
    host: str = "database"
    port: int = 5432
    user: str = ""
    password: str = ""
    name: str = ""
    schema: str = "public"
    tables: dict = {}


class ApiConfig(BaseModel):
    enable: bool = True
    host: str = "0.0.0.0"
    port: int = 8081
    api_key: str = ""


class MetricsConfig(BaseModel):
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
        env_file=".env"
    )

    logging: LoggingConfig = LoggingConfig()
    files: FilesConfig = FilesConfig()
    bot: BotConfig = BotConfig()
    backend: BackendConfig = BackendConfig()
    api: ApiConfig = ApiConfig()
    modules: ModulesConfig = ModulesConfig()
    metrics: MetricsConfig = MetricsConfig()
    database: DatabaseConfig = DatabaseConfig()

    _yaml_file: ClassVar[str] = "./config.yaml"

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
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=cls._yaml_file),
        )
