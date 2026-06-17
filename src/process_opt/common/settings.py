from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROCESS_OPT_")

    gateway_api_key: str = "dev-api-key"
    nats_url: str = "nats://localhost:4222"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/process_opt"
    nats_stream: str = "PROCESS_OPT"
    process_subject: str = "process_data"
    inspection_subject: str = "inspection_data"

    # Container pool settings
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_image: str = "opencode-web"
    pool_base_port: int = 5101
    pool_network: str = "thingsboard_default"
    session_ttl_seconds: int = 1800
    health_check_interval_seconds: int = 120
    docker_host_ip: str = "127.0.0.1"
