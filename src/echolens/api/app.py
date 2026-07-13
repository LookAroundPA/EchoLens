"""FastAPI application factory for the EchoLens frontend backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from echolens.api.models import HealthResponse
from echolens.api.routes import router
from echolens.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the read-only EchoLens HTTP API."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title="EchoLens API",
        description="Read-only API for creators, videos, transcripts, and analyses.",
        version="0.1.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.parsed_api_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix="/api")

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
