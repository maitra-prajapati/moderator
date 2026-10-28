"""M4-local Pydantic definitions that mirror frozen B.2/B.3/B.4 contracts."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Source(Strict):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    valid_until: str | None


class Rule(Strict):
    id: str = Field(min_length=1)
    type: Literal["terminology", "restricted_phrase"]
    pattern: str = Field(min_length=1, max_length=200)
    replacement: str | None
    severity: Literal["info", "warning", "blocker"]
    source_id: str | None


class Claim(Strict):
    id: str = Field(min_length=1)
    fact_key: str = Field(min_length=1)
    value: int = Field(ge=0)
    unit: str = Field(min_length=1)
    approved_text: str = Field(min_length=1)
    source_id: str = Field(min_length=1)


class Knowledge(Strict):
    brand_id: str = Field(min_length=1)
    knowledge_version_id: str = Field(min_length=1)
    version_no: int = Field(ge=1)
    activated_at: str = Field(min_length=1)
    voice_traits: list[str] = Field(max_length=100)
    sources: list[Source] = Field(max_length=500)
    rules: list[Rule] = Field(max_length=500)
    claims: list[Claim] = Field(max_length=500)

    @model_validator(mode="after")
    def unique_identifiers(self):
        for label, values in (
            ("source", [s.id for s in self.sources]),
            ("rule", [r.id for r in self.rules]),
            ("claim", [c.id for c in self.claims]),
            ("fact_key", [c.fact_key for c in self.claims]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(
                    f"Duplicate {label} in knowledge snapshot"
                )
        return self


class AnalysisRequest(Strict):
    request_id: str = Field(min_length=1)
    submission_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    channel: Literal["linkedin", "website", "email"]
    text: str = Field(min_length=1, max_length=10_000)
    knowledge: Knowledge
    ai_enabled: bool


class Span(Strict):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str


class Finding(Strict):
    finding_id: str
    category: Literal[
        "terminology",
        "restricted_phrase",
        "claim_mismatch",
        "unsupported_claim",
        "tone",
    ]
    severity: Literal["info", "warning", "blocker"]
    evidence_status: Literal[
        "supported",
        "contradicted",
        "needs_verification",
        "not_applicable",
    ]
    span: Span
    rule_id: str | None
    claim_id: str | None
    source_id: str | None
    knowledge_version_id: str
    explanation: str
    suggested_replacement: str | None
    confidence_kind: Literal[
        "deterministic",
        "ai_assisted",
    ]


class AnalysisResponse(Strict):
    request_id: str
    submission_id: str
    revision_id: str
    findings: list[Finding] = Field(max_length=500)