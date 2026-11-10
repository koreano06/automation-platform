from fastapi import APIRouter

from app.api.endpoints import (
    assets,
    auth,
    callbacks,
    health,
    operations,
    platforms,
    provisioning,
    studio,
)

api_router = APIRouter()
for module in [health, auth, platforms, provisioning, callbacks, operations, assets, studio]:
    api_router.include_router(module.router)
