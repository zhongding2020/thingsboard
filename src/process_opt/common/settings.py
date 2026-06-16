from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROCESS_OPT_")

    gateway_api_key: str = "dev-api-key"
    nats_url: str = "nats://localhost:4222"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/process_opt"
    nats_stream: str = "PROCESS_OPT"
    process_subject: str = "process_data"
    inspection_subject: str = "inspection_data"
    openai_api_key: str = ""
    openai_model: str = ""
    openai_base_url: str = ""
