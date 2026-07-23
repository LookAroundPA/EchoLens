"""FastAPI dependencies for EchoLens HTTP endpoints."""

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends

from echolens.api.content_service import ContentService
from echolens.api.intelligence_management_service import IntelligenceManagementService
from echolens.api.intelligence_service import IntelligenceApiService
from echolens.api.knowledge_service import KnowledgeService
from echolens.api.management_service import ManagementService
from echolens.api.queued_operations import QueuedOperationService
from echolens.api.service import FrontendService
from echolens.storage.content_repository import ContentRepository
from echolens.storage.frontend_repository import FrontendRepository
from echolens.storage.intelligence_management_repository import (
    IntelligenceManagementRepository,
)
from echolens.storage.intelligence_query_repository import IntelligenceQueryRepository
from echolens.storage.maintenance import DatabaseMaintenance
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


def get_operation_service() -> QueuedOperationService:
    """Create jobs in MySQL and submit them to the independent Redis worker."""

    return QueuedOperationService()


def get_intelligence_api_service() -> Iterator[IntelligenceApiService]:
    """Open one MySQL connection for topic intelligence reads."""

    with mysql_connection() as connection:
        yield IntelligenceApiService(IntelligenceQueryRepository(connection))


def get_intelligence_management_service() -> Iterator[IntelligenceManagementService]:
    """Open one transactional MySQL connection for controlled topic maintenance."""

    with mysql_connection() as connection:
        DatabaseMaintenance(connection).ensure_intelligence_schema()
        yield IntelligenceManagementService(IntelligenceManagementRepository(connection))


@lru_cache(maxsize=1)
def _shared_knowledge_service() -> KnowledgeService:
    """Keep the local embedding model warm across API requests."""

    return KnowledgeService()


def get_knowledge_service() -> KnowledgeService:
    return _shared_knowledge_service()
