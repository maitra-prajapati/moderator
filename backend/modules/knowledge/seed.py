"""Seed a single fictional brand; safe to run more than once."""
from .database import make_session_factory
from .models import Brand
from .schemas import knowledgedraft
from .service import create_draft, activate



FLOWPILOT = {
    "voice_traits": ["friendly", "professional", "precise"],
    "sources": [
        {"id": "src_trial", "title": "Demo Trial Policy",
         "excerpt": "FlowPilot offers a 14-day free trial.", "valid_until": None},
        {"id": "src_names", "title": "Demo Brand Guide",
         "excerpt": "Official product spelling: FlowPilot.", "valid_until": None},
    ],
    "rules": [
        {"id": "rule_name", "type": "terminology", "pattern": "Flow Pilot",
         "replacement": "FlowPilot", "severity": "warning", "source_id": "src_names"},
        {"id": "rule_guarantee", "type": "restricted_phrase", "pattern": "100% guaranteed",
         "replacement": None, "severity": "blocker", "source_id": None},
    ],
    "claims": [
        {"id": "claim_trial", "fact_key": "free_trial_days", "value": 14,
         "unit": "days", "approved_text": "14-day free trial", "source_id": "src_trial"},
    ],
}




def seed(session_factory=None):
    factory = session_factory or make_session_factory()
    with factory() as session:
        if session.get(Brand, "brand_flowpilot") is None:
            session.add(Brand(id="brand_flowpilot", display_name="FlowPilot Demo (Fictional)"))
            session.commit()
        from .service import get_active_snapshot, knowledge_error
        try:
            return get_active_snapshot(session, "brand_flowpilot")
        except knowledge_error:
            pass
        draft = create_draft(session, "brand_flowpilot", knowledgedraft.model_validate(FLOWPILOT))
        return activate(session, "brand_flowpilot", draft["version_no"])




if __name__ == "__main__":
    snapshot = seed()
    print(f"Seeded {snapshot['brand_id']} / version {snapshot['version_no']}")

