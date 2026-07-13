"""FastAPI dependencies for database-backed read endpoints."""

from collections.abc import Iterator

from fastapi import Depends

from echolens.api.service import FrontendService
from echolens.storage.frontend_repository import FrontendRepository
from echolens.storage.mysql import mysql_connection


def get_frontend_repository() -> Iterator[FrontendRepository]:
    """Open one MySQL connection for the duration of an HTTP request."""

    with mysql_connection() as connection:
        yield FrontendRepository(connection)


def get_frontend_service(
    repository: FrontendRepository = Depends(get_frontend_repository),
) -> FrontendService:
    return FrontendService(repository)
