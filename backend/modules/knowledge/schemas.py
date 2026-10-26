from typing import Literal
from pydantic import BaseModel , ConfigDict, Field

class strictmodel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class source(strictmodel):
    id:str = Field(min_length=1)
    title:str = Field(min_length= 1)
    excerpt:str = Field(min_length= 1)
    valid_until : str | None = None



class rule(strictmodel):
    id: str = Field(min_length=1)
    type: Literal["terminology", "restricted_phrase"]
    pattern: str = Field(min_length=1)
    replacement: str | None
    severity: Literal["info", "warning", "blocker"]
    source_id: str | None


class claim(strictmodel):
    id: str = Field(min_length=1)
    fact_key: str = Field(min_length=1)
    value: int = Field(ge=0)
    unit: str = Field(min_length=1)
    approved_text: str = Field(min_length=1)
    source_id: str = Field(min_length=1)


class knowledgedraft(strictmodel):
    voice_traits: list[str] = Field(min_length=1)
    sources: list[source] = Field(min_length=1)
    rules: list[rule] = Field(default_factory=list)
    claims: list[claim] = Field(default_factory=list)

    