import uvicorn
from fastapi import FastAPI

from process_opt.common.nats_client import JetStreamPublisher
from process_opt.common.settings import Settings
from process_opt.gateway.app import create_app


def create_gateway_app_from_settings() -> FastAPI:
    return create_app(Settings(), JetStreamPublisher(Settings()))


def main() -> None:
    uvicorn.run(create_gateway_app_from_settings(), host="0.0.0.0", port=8001)
