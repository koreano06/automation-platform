from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.version import BUILD_ID

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    version: str
    environment: str
    build_id: str
    capabilities: list[str]


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        build_id=BUILD_ID,
        capabilities=[
            "platform_delete",
            "step_tests",
            "worker_health",
            "flow_conditions",
            "operator_controls",
        ],
    )
