from dataclasses import dataclass
from typing import Any, Callable, Protocol

Json = dict[str, Any]


class AuthPort(Protocol):
    def login(self, email: str, password: str) -> Json: ...
    def me(self, token: str) -> Json: ...
    def users(self, actor: Json) -> list[Json]: ...
    def create_user(self, actor: Json, data: Json) -> Json: ...
    def brands(self, actor: Json, user_id: str, brand_ids: list[str]) -> Json: ...
    def permissions(
        self, actor: Json, user_id: str, changes: Json
    ) -> Json: ...


class KnowledgePort(Protocol):
    def by_version(self, brand_id: str, version_id: str) -> Json: ...
    def active(self, brand_id: str) -> Json: ...
    def draft(self, brand_id: str, data: Json) -> Json: ...
    def activate(
        self, brand_id: str, version_no: int
    ) -> Json: ...


class WorkflowPort(Protocol):
    def create(self, data: Json, actor: Json) -> Json: ...
    def list_for(self, actor: Json) -> list[Json]: ...
    def get(
        self, submission_id: str, actor: Json
    ) -> Json: ...
    def revise(
        self, submission_id: str, text: str, actor: Json
    ) -> Json: ...

    def begin_analysis(
        self,
        submission_id: str,
        actor: Json,
        version_id: str,
    ) -> Json: ...

    def save_analysis(
        self,
        submission_id: str,
        revision_id: str,
        request_id: str,
        findings: list[Json],
        actor: Json,
    ) -> Json: ...

    def fail_analysis(
        self,
        submission_id: str,
        revision_id: str,
        request_id: str,
        reason: str,
        actor: Json,
    ) -> None: ...

    def findings(
        self,
        submission_id: str,
        revision_id: str | None,
        actor: Json,
    ) -> Json: ...

    def finding_action(
        self,
        submission_id: str,
        finding_id: str,
        action: str,
        reason: str | None,
        actor: Json,
    ) -> Json: ...

    def review(
        self,
        submission_id: str,
        decision: str,
        comment: str,
        actor: Json,
    ) -> Json: ...

    def history(
        self, submission_id: str, actor: Json
    ) -> list[Json]: ...

    def analytics_models(self, actor: Json) -> Json: ...


@dataclass(frozen=True)
class Ports:
    auth: AuthPort
    knowledge: KnowledgePort
    workflow: WorkflowPort
    analyse: Callable[[Json], Json]
    summarise: Callable[[Json], Json]