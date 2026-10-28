from backend.modules.knowledge.database import (
    make_session_factory,
)
from backend.modules.knowledge.schemas import (
    knowledgedraft,
)
from sqlalchemy import select
from backend.modules.knowledge.models import knowledge_version
from backend.modules.knowledge.service import (
    knowledge_error,
    _snapshot,
    activate,
    create_draft,
    get_active_snapshot,
)


class KnowledgeAdapter:
    def __init__(
        self, database_url: str | None = None
    ):
        self.sessions = make_session_factory(database_url)

    def active(self, brand_id: str) -> dict:
        with self.sessions() as session:
            return get_active_snapshot(
                session, brand_id
            )

    def by_version(self, brand_id: str, version_id: str) -> dict:
        with self.sessions() as session:
            row = session.scalar(
                select(knowledge_version).where(
                    knowledge_version.id == version_id,
                    knowledge_version.brand_id == brand_id,
                    knowledge_version.status == "ACTIVATED",
                )
            )
            if row is None:
                raise knowledge_error(404, "KNOWLEDGE_NOT_FOUND", "Activated version not found")
            return _snapshot(row)

    def draft(
        self, brand_id: str, data: dict
    ) -> dict:
        with self.sessions() as session:
            return create_draft(
                session,
                brand_id,
                knowledgedraft.model_validate(data),
            )

    def activate(
        self, brand_id: str, version_no: int
    ) -> dict:
        with self.sessions() as session:
            return activate(
                session, brand_id, version_no
            )