"""M3-owned JSON/Pydantic contracts; no imports from identity/knowledge/analysis."""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class Actor:
    id: str
    role: str
    can_create: bool = False
    can_review: bool = False
    can_approve: bool = False
    can_manage_knowledge: bool = False
    can_manage_users: bool = False


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class SubmissionCreate(Strict):
    brand_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    channel: Literal['linkedin', 'website', 'email']
    text: str = Field(min_length=1, max_length=10000)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.brand_id.strip() or not self.title.strip() or not self.text.strip():
            raise ValueError('brand_id, title and text cannot be blank')
        return self


class RevisionCreate(Strict):
    text: str = Field(min_length=1, max_length=10000)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.text.strip():
            raise ValueError('Text cannot be blank')
        return self


class Span(Strict):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str


class FindingIn(Strict):
    finding_id: str = Field(min_length=1)
    category: Literal['terminology', 'restricted_phrase', 'claim_mismatch', 'unsupported_claim', 'tone']
    severity: Literal['info', 'warning', 'blocker']
    evidence_status: Literal['supported', 'contradicted', 'needs_verification', 'not_applicable']
    span: Span
    rule_id: str | None
    claim_id: str | None
    source_id: str | None
    knowledge_version_id: str
    explanation: str = Field(min_length=1)
    suggested_replacement: str | None
    confidence_kind: Literal['deterministic', 'ai_assisted']


class AnalysisResponse(Strict):
    request_id: str
    submission_id: str
    revision_id: str
    findings: list[FindingIn] = Field(max_length=500)


class ReviewRequest(Strict):
    decision: Literal['approve', 'request_changes', 'reject', 'override_approve']
    comment: str = Field(max_length=2000)

    @model_validator(mode='after')
    def reason(self):
        if self.decision in ('request_changes', 'reject', 'override_approve') and not self.comment.strip():
            raise ValueError('A reason is required for this decision')
        return self


class FindingActionRequest(Strict):
    action: Literal['acknowledge', 'accept_suggestion', 'dismiss']
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def reason_for_dismissal(self):
        if self.action == 'dismiss' and not (self.reason and self.reason.strip()):
            raise ValueError('Dismissal requires an explanation')
        return self