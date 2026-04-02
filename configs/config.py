from pydantic_settings import BaseSettings, SettingsConfigDict

_base_config = SettingsConfigDict(
    env_file='./.env',
    env_ignore_empty=True,
    extra="ignore"
)

class APIKeys(BaseSettings):
    SERPAPI_API_KEY: str 

    model_config = _base_config

api_keys = APIKeys()