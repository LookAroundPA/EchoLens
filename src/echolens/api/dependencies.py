"""FastAPI dependencies for EchoLens HTTP endpoints."""

from collections.abc import Iterator

from fastapi import Depends

from echolens.api.content_service import ContentService
from echolens.api.management_service import ManagementService
from echolens.api.operations import OperationService
from echolens.api.progress_operations import ProgressOperationService
from echolens.api.service import FrontendService
from echolens.storage.content_repository import ContentRepository
from echolens.storage.frontend_repository import FrontendRepository
from echolens.storage.management_repository import ManagementRepository
from echolens.storage.mysql import mysql_connection


def get_frontend_repository() -> Iterator[FrontendRepository]:
    """Open one MySQL connection for a read request."""

    with mysql_connection() as connection:
        yield FrontendRepository(connection)


def get_frontend_service(
    repository: FrontendRepository = Depends(get_frontend_repository),
) -> FrontendService:
    return FrontendService(repository)


def get_content_service() -> Iterator[ContentService]:
    """Share one committed MySQL connection across video writes and rereads."""

    with mysql_connection() as connection:
        yield ContentService(
            ContentRepository(connection),
            FrontendRepository(connection),
        )


def get_management_repository() -> Iterator[ManagementRepository]:
    """Open one MySQL connection for catalog and action validation."""

    with mysql_connection() as connection:
        yield ManagementRepository(connection)


def get_management_service(
    repository: ManagementRepository = Depends(get_management_repository),
) -> ManagementService:
    return ManagementService(repository)


def get_operation_service() -> OperationService:
    """Return the progress-aware service; background jobs open their own connections."""

    return ProgressOperationService()
