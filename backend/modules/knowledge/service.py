from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Brand, knowledge_version
from .schemas import knowledgedraft

class knowledge_error(Exception):
    def __init__(self, status_code:int, code:str, message:str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _unique(values:list[str], category:str) -> None:
    if len(values) != len(set(values)):
        raise knowledge_error(422, "INVALID_KNOWLEDGE", F"Duplicate {category} identifiers")


def _check_references(draft: knowledgedraft) -> None:
    """Check IDs, source expiry, and duplicate structured facts."""

    _unique([s.id for s in draft.sources], "source")
    _unique([r.id for r in draft.rules], "rule")
    _unique([c.id for c in draft.claims], "claim")
    _unique([c.fact_key for c in draft.claims], "fact_key")

    today = datetime.now(timezone.utc).date()
    source_by_id = {}

    for source in draft.sources:
        if source.valid_until is not None:
            try:
                expiry = date.fromisoformat(source.valid_until)
            except ValueError:
                raise knowledge_error(
                    422, "INVALID_KNOWLEDGE",
                    f"Source {source.id}: valid_until must be YYYY-MM-DD or null",
                ) from None
            if expiry < today:
                # Keep expired sources in the draft for visibility, but reject their
                # use as authoritative evidence at activation.
                source_by_id[source.id] = False
                continue
        source_by_id[source.id] = True


    for claim in draft.claims:
        if claim.source_id not in source_by_id:
            raise knowledge_error(422, "INVALID_KNOWLEDGE", f"Claim {claim.id}: missing source {claim.source_id}")
        if not source_by_id[claim.source_id]:
            raise knowledge_error(422, "EXPIRED_SOURCE", f"Claim {claim.id}: source {claim.source_id} has expired")


    for rule in draft.rules:
        if rule.source_id is not None and rule.source_id not in source_by_id:
            raise knowledge_error(422, "INVALID_KNOWLEDGE", f"Rule {rule.id}: missing source {rule.source_id}")
        if rule.source_id is not None and not source_by_id[rule.source_id]:
            raise knowledge_error(422, "EXPIRED_SOURCE", f"Rule {rule.id}: source {rule.source_id} has expired")



def create_draft(session: Session , brand_id: str, draft: knowledgedraft) -> dict:
    if session.get(Brand, brand_id) is None:
        raise knowledge_error(404, "BRAND_NOT_FOUND", f"Unknown brand: {brand_id}")

    latest = session.scalar(
        select(func.max(knowledge_version.version_no)).where(knowledge_version.brand_id == brand_id)
    )


    version_no = (latest or 0) + 1
    version_id = f"kv_{brand_id}_{version_no:03d}"
    row = knowledge_version(
        id=version_id, brand_id=brand_id, version_no=version_no,
        status="DRAFT", payload=draft.model_dump(mode="json"), activated_at=None,
    )
    session.add(row)
    session.commit()
    return {"brand_id": brand_id, "knowledge_version_id": version_id,
            "version_no": version_no, "status": "DRAFT"}



def activate(session: Session, brand_id: str, version_no: int) -> dict:
    row = session.scalar(
        select(knowledge_version).where(
            knowledge_version.brand_id == brand_id,
            knowledge_version.version_no == version_no,
        )
    )



    if row is None:
        raise knowledge_error(404, "VERSION_NOT_FOUND", "Knowledge version not found")
    if row.status != "DRAFT":
        raise knowledge_error(409, "IMMUTABLE_VERSION", "Activated versions cannot be changed or activated again")


    newest_activated = session.scalar(
        select(func.max(knowledge_version.version_no)).where(
            knowledge_version.brand_id == brand_id,
            knowledge_version.status == "ACTIVATED",
        )
    )

    if newest_activated is not None and version_no < newest_activated:
        raise knowledge_error(409, "STALE_VERSION", "Cannot activate a version older than the current active version")


    _check_references(knowledgedraft.model_validate(row.payload))
    row.status = "ACTIVATED"
    row.activated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    session.commit()
    return _snapshot(row)


def _snapshot(row: knowledge_version) -> dict:

    return {
        "brand_id": row.brand_id,
        "knowledge_version_id": row.id,
        "version_no": row.version_no,
        "activated_at": row.activated_at,
        **row.payload,
    }


def get_active_snapshot(session: Session, brand_id: str) -> dict:
    row = session.scalar(
        select(knowledge_version).where(
            knowledge_version.brand_id == brand_id,
            knowledge_version.status == "ACTIVATED",
        ).order_by(knowledge_version.version_no.desc()).limit(1)
    )
    if row is None:
        raise knowledge_error(404, "KNOWLEDGE_NOT_FOUND", "No activated knowledge for this brand")
    return _snapshot(row)



