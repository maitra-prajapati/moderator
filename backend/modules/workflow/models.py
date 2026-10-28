"""M3-owned SQLAlchemy metadata and tables. Do not import other modules."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import ForeignKey, UniqueConstraint, String, Integer, Text, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


def new_id(prefix: str):
    return f"{prefix}_{uuid4().hex}"


class Base(DeclarativeBase):
    pass


class Submission(Base):
    __tablename__ = 'workflow_submissions'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default='DRAFT')
    current_revision_id: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Revision(Base):
    __tablename__ = 'workflow_revisions'
    __table_args__ = (UniqueConstraint('submission_id', 'revision_no'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey('workflow_submissions.id'), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AnalysisRun(Base):
    __tablename__ = 'workflow_analysis_runs'
    __table_args__ = (UniqueConstraint('revision_id', 'attempt_no'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey('workflow_submissions.id'), nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey('workflow_revisions.id'), nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_version_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ANALYZING/FAILED/COMPLETED
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Finding(Base):
    __tablename__ = 'workflow_findings'
    __table_args__ = (UniqueConstraint('analysis_run_id', 'external_finding_id'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    external_finding_id: Mapped[str] = mapped_column(String(120), nullable=False)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey('workflow_analysis_runs.id'), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey('workflow_submissions.id'), nullable=False)
    revision_id: Mapped[str] = mapped_column(ForeignKey('workflow_revisions.id'), nullable=False, index=True)
    knowledge_version_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(30), nullable=False)
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(120))
    claim_id: Mapped[str | None] = mapped_column(String(120))
    source_id: Mapped[str | None] = mapped_column(String(120))
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_replacement: Mapped[str | None] = mapped_column(Text)
    confidence_kind: Mapped[str] = mapped_column(String(20), nullable=False)


class FindingAction(Base):
    __tablename__ = 'workflow_finding_actions'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey('workflow_findings.id'), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Review(Base):
    __tablename__ = 'workflow_reviews'
    __table_args__ = (UniqueConstraint('revision_id'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey('workflow_submissions.id'), nullable=False)
    revision_id: Mapped[str] = mapped_column(ForeignKey('workflow_revisions.id'), nullable=False, index=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey('workflow_analysis_runs.id'), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditEvent(Base):
    __tablename__ = 'workflow_audit_events'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    submission_id: Mapped[str] = mapped_column(ForeignKey('workflow_submissions.id'), nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey('workflow_revisions.id'), nullable=False)
    knowledge_version_id: Mapped[str | None] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column('metadata', JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)