import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.api.router import api_router
from app.core.config import settings
from app.database.migrations import check_schema

logger = logging.getLogger("automation.api")


def create_app(verify_schema=True):
    @asynccontextmanager
    async def lifespan(_):
        if verify_schema:
            check_schema()
        if settings.environment == "production" and not settings.cookie_secure:
            raise RuntimeError("Produção exige COOKIE_SECURE=true e HTTPS.")
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Provisionamento e acompanhamento de cadastros.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "Idempotency-Key",
            "X-Callback-Timestamp",
            "X-Callback-Signature",
        ],
    )

    @application.middleware("http")
    async def headers(request: Request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 262144:
            return JSONResponse({"detail": "Requisição muito grande."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exception: RequestValidationError):
        # Pydantic's default error includes the submitted input, which may contain secrets.
        return JSONResponse(
            {
                "detail": [
                    {
                        "loc": list(error["loc"]),
                        "type": error["type"],
                        "msg": "Valor inválido para este campo.",
                    }
                    for error in exception.errors()
                ]
            },
            status_code=422,
        )

    @application.exception_handler(IntegrityError)
    async def conflict(_: Request, __: IntegrityError):
        return JSONResponse(
            {"detail": "Conflito de dados: nome, versão ou execução pendente já existente."},
            status_code=409,
        )

    @application.exception_handler(StaleDataError)
    async def concurrent_update(_: Request, __: StaleDataError):
        return JSONResponse(
            {
                "detail": "A execução foi atualizada por outro processo. Consulte o estado e repita a operação."
            },
            status_code=409,
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, __: SQLAlchemyError):
        logger.error("Falha na persistência; conteúdo da consulta omitido.")
        return JSONResponse({"detail": "Não foi possível persistir a operação."}, status_code=503)

    application.include_router(api_router)
    return application


app = create_app()
