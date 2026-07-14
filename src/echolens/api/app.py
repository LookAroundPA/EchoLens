"""FastAPI application factory for the EchoLens frontend backend."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from echolens.api.batch_routes import router as batch_router
from echolens.api.content_routes import router as content_router
from echolens.api.models import HealthResponse
from echolens.api.queued_operations import JobQueueUnavailable
from echolens.api.retry_routes import router as retry_router
from echolens.api.routes import router
from echolens.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the EchoLens HTTP API."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title="EchoLens API",
        description="Frontend API for browsing and operating the EchoLens content pipeline.",
        version="0.7.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.parsed_api_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix="/api")
    application.include_router(retry_router, prefix="/api")
    application.include_router(batch_router, prefix="/api")
    application.include_router(content_router, prefix="/api")

    @application.exception_handler(JobQueueUnavailable)
    def operation_queue_unavailable(
        _request: Request,
        error: JobQueueUnavailable,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
