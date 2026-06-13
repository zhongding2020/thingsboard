from fastapi import FastAPI
from fastapi.routing import APIRoute

from process_opt.api.main import create_api_app_from_settings
from process_opt.gateway.main import create_gateway_app_from_settings


def test_create_gateway_app_from_settings_returns_fastapi_app() -> None:
    app = create_gateway_app_from_settings()

    assert isinstance(app, FastAPI)


def test_create_api_app_from_settings_returns_fastapi_app() -> None:
    app = create_api_app_from_settings()

    assert isinstance(app, FastAPI)
    assert any(isinstance(route, APIRoute) and route.path == "/health" for route in app.routes)
