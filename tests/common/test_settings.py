from process_opt.common.settings import Settings


def test_settings_loads_defaults() -> None:
    settings = Settings()
    assert settings.gateway_api_key == "dev-api-key"
    assert settings.nats_url == "nats://localhost:4222"
    assert settings.postgres_dsn == "postgresql://postgres:postgres@localhost:5432/process_opt"
