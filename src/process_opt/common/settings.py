from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROCESS_OPT_")

    gateway_api_key: str = "dev-api-key"
    gateway_url: str = "http://localhost:8001"
    nats_url: str = "nats://localhost:4222"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/process_opt"
    nats_stream: str = "PROCESS_OPT"
    process_subject: str = "process_data"
    inspection_subject: str = "inspection_data"

    # Agent settings
    agent_model: str = "ark-code-latest"
    agent_api_base: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    agent_api_key: str = ""
    agent_temperature: float = 0.0
    agent_session_ttl: int = 1800
