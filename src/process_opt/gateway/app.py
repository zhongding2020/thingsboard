from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from process_opt.common.errors import PublishError
from process_opt.common.nats_client import Publisher
from process_opt.common.schemas import InspectionMessage, ProcessMessage
from process_opt.common.settings import Settings


def create_app(settings: Settings, publisher: Publisher) -> FastAPI:
    app = FastAPI()

    async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if x_api_key != settings.gateway_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    @app.post("/api/v1/data/process", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_process(message: ProcessMessage, _: Annotated[None, Depends(require_api_key)]) -> dict[str, str]:
        try:
            await publisher.publish(settings.process_subject, message.model_dump(mode="json"))
        except PublishError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Publish failed") from exc
        return {"status": "accepted"}

    @app.post("/api/v1/data/inspection", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_inspection(message: InspectionMessage, _: Annotated[None, Depends(require_api_key)]) -> dict[str, str]:
        try:
            await publisher.publish(settings.inspection_subject, message.model_dump(mode="json"))
        except PublishError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Publish failed") from exc
        return {"status": "accepted"}

    return app
