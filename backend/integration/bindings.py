import os
from importlib import import_module

from .gateway import ApiFault
from .knowledge_adapter import KnowledgeAdapter
from .ports import Ports


class MissingPort:
    def __init__(self, name: str):
        self.name = name

    def __getattr__(self, method: str):
        def unavailable(*_args, **_kwargs):
            raise ApiFault(
                503,
                "ADAPTER_NOT_CONFIGURED",
                f"{self.name} adapter not configured",
            )

        return unavailable


def load_factory(value: str, name: str):
    if not value:
        return MissingPort(name)

    module_name, delimiter, function_name = (
        value.partition(":")
    )

    if (
        not delimiter
        or not module_name
        or not function_name
    ):
        raise RuntimeError(
            f"{name} must look like "
            "package.module:factory_function"
        )

    return getattr(
        import_module(module_name),
        function_name,
    )()


def build_ports() -> Ports:
    from backend.modules.insights import summarise

    def run_m4(request: dict) -> dict:
        from backend.modules.analysis.engine import analyse

        return analyse(request)

    return Ports(
        auth=load_factory(
            os.getenv("MODERATOR_M2_FACTORY", "backend.integration.m2_bridge:make_auth_port"),
            "M2",
        ),
        workflow=load_factory(
            os.getenv("MODERATOR_M3_FACTORY", "backend.integration.m3_bridge:make_workflow_port"),
            "M3",
        ),
        knowledge=KnowledgeAdapter(
            os.getenv("MODERATOR_KNOWLEDGE_DB_URL")
        ),
        analyse=run_m4,
        summarise=summarise,
    )