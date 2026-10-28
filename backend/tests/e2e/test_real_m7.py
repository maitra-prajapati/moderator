"""Real SQLite end-to-end M1–M4+M6+M7, not contract doubles."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from backend.integration.m2_bridge import AuthAdapter, USER_BRANDS
from backend.integration.m3_bridge import WorkflowAdapter
from backend.integration.knowledge_adapter import KnowledgeAdapter
from backend.integration.ports import Ports
from backend.integration.gateway import make_app
from backend.modules.auth.models import User
from backend.modules.auth.security import hash_password
from backend.modules.knowledge.seed import seed
from backend.modules.insights import summarise
from backend.modules.analysis.engine import analyse
from backend.modules.workflow.models import AnalysisRun


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MODERATOR_JWT_SECRET", "test-not-a-live-secret-123456789-123456789-ABC")
    k_url = f"sqlite+pysqlite:///{tmp_path/'auth_knowledge.sqlite'}"
    w_url = f"sqlite+pysqlite:///{tmp_path/'workflow.sqlite'}"
    knowledge = KnowledgeAdapter(k_url)
    seed(knowledge.sessions)
    auth = AuthAdapter(k_url)
    wf = WorkflowAdapter(w_url)
    ids = {}
    with auth.sessions() as session:
        for role in ("creator", "reviewer", "admin", "isolated"):
            r = "creator" if role == "isolated" else role
            user = User(email=f"{role}@flowpilot.demo", role=r, password_hash=hash_password("Password#12345"))
            session.add(user)
            session.flush()
            ids[role] = user.id
            if role != "isolated":
                session.execute(insert(USER_BRANDS).values(user_id=user.id, brand_id="brand_flowpilot"))
        session.commit()
    ports = Ports(auth=auth, workflow=wf, knowledge=knowledge, analyse=analyse, summarise=summarise)
    app = make_app(ports)
    client = TestClient(app, raise_server_exceptions=False)
    headers = {}
    for role in ids:
        response = client.post("/api/v1/auth/login", json={
            "email": f"{role}@flowpilot.demo", "password": "Password#12345"
        })
        assert response.status_code == 200, response.text
        headers[role] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return client, headers, ids, auth, wf, knowledge


def create(client, headers, text="Flow Pilot offers a 30-day free trial and 100% guaranteed results."):
    response = client.post("/api/v1/submissions", headers=headers["creator"], json={
        "brand_id": "brand_flowpilot", "title": "Marketing copy", "channel": "linkedin", "text": text,
    })
    assert response.status_code == 201, response.text
    return response.json()["submission_id"]


def test_real_create_submit_analyse_findings_review_override_analytics(env):
    client, h, ids, auth, wf, knowledge = env
    sub = create(client, h)
    created = client.get(f"/api/v1/submissions/{sub}", headers=h["creator"]).json()
    assert created["state"] == "DRAFT"
    submitted = client.post(f"/api/v1/submissions/{sub}/submit", headers=h["creator"])
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["state"] == "REVIEW_REQUIRED"
    assert body["request_id"].startswith("req_")
    assert body["finding_counts"]["blocker"] >= 1
    with wf.sessions() as session:
        assert session.get(AnalysisRun, body["request_id"]).status == "COMPLETED"
    again = client.post(f"/api/v1/submissions/{sub}/submit", headers=h["creator"])
    assert again.status_code == 200
    assert again.json()["request_id"] == body["request_id"]
    findings = client.get(f"/api/v1/submissions/{sub}/findings", headers=h["creator"]).json()
    assert findings["analysis_status"] == "COMPLETED"
    assert len(findings["findings"]) >= 3
    assert client.post(f"/api/v1/submissions/{sub}/reviews", headers=h["reviewer"], json={"decision": "approve", "comment": "Reviewed"}).status_code == 409
    assert client.post(f"/api/v1/submissions/{sub}/reviews", headers=h["creator"], json={"decision": "override_approve", "comment": "Tried self approval"}).status_code == 403
    approved = client.post(f"/api/v1/submissions/{sub}/reviews", headers=h["admin"], json={"decision": "override_approve", "comment": "Approved exception for synthetic test"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "APPROVED"
    history = client.get(f"/api/v1/submissions/{sub}/history", headers=h["reviewer"]).json()
    assert any(e["event_type"] == "review.override_approved" for e in history)
    analytics = client.get("/api/v1/analytics/summary", headers=h["reviewer"])
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["approved"] == 1
    assert analytics.json()["reviews"]["blocker_overrides"] == 1
    assert analytics.json()["findings"]["total"] >= 3


def test_real_permissions_brand_scope_and_user_admin(env):
    client, h, ids, auth, wf, knowledge = env
    sub = create(client, h)
    assert client.get(f"/api/v1/submissions/{sub}", headers=h["isolated"]).status_code == 403
    assert client.get("/api/v1/submissions", headers=h["isolated"]).json() == []
    assert client.get("/api/v1/analytics/summary", headers=h["isolated"]).json()["total"] == 0
    assert client.post("/api/v1/submissions", headers=h["reviewer"], json={
        "brand_id":"brand_flowpilot","title":"No","channel":"email","text":"Hello"
    }).status_code == 403
    assert client.patch(f"/api/v1/admin/users/{ids['reviewer']}/permissions", headers=h["creator"], json={"can_create":True}).status_code == 403
    change = client.patch(f"/api/v1/admin/users/{ids['reviewer']}/permissions", headers=h["admin"], json={"can_create":True})
    assert change.status_code == 200, change.text
    assert change.json()["permissions"]["can_create"] is True
    # Admin grants brand access to previously isolated creator.
    grant = client.put(f"/api/v1/admin/users/{ids['isolated']}/brands", headers=h["admin"], json={"brand_ids": ["brand_flowpilot"]})
    assert grant.status_code == 200, grant.text
    assert client.get(f"/api/v1/submissions/{sub}", headers=h["isolated"]).status_code == 403  # Still not the author.
    assert client.post("/api/v1/submissions", headers=h["isolated"], json={
        "brand_id":"brand_flowpilot", "title":"Allowed", "channel":"email", "text":"Hello"
    }).status_code == 201
    me = client.get("/api/v1/auth/me", headers=h["isolated"]).json()
    assert "brand_ids" not in me
    assert "password_hash" not in str(me)


def test_real_analysis_failure_retry_and_revision_preserves_audit(env):
    client, h, ids, auth, wf, knowledge = env
    sub = create(client, h, "FlowPilot is the best solution.")
    original = wf.get(sub, auth.me(h["creator"]["Authorization"].split()[-1]))
    original_text = original["text"]
    # Cause validation failure in M7, then retry using the frozen version.
    ports = Ports(auth=auth, workflow=wf, knowledge=knowledge,
                  analyse=lambda request: {"request_id": "wrong", "findings": []}, summarise=summarise)
    bad_client = TestClient(make_app(ports), raise_server_exceptions=False)
    failed = bad_client.post(f"/api/v1/submissions/{sub}/submit", headers=h["creator"])
    assert failed.status_code == 500, failed.text
    assert failed.json()["error"]["code"] == "ANALYSIS_FAILED"
    assert client.get(f"/api/v1/submissions/{sub}", headers=h["creator"]).json()["state"] == "ANALYSIS_FAILED"
    retried = client.post(f"/api/v1/submissions/{sub}/submit", headers=h["creator"])
    assert retried.status_code == 200, retried.text
    assert retried.json()["state"] == "REVIEW_REQUIRED"
    detail = client.get(f"/api/v1/submissions/{sub}", headers=h["creator"]).json()
    assert detail["text"] == original_text
    audit = client.get(f"/api/v1/submissions/{sub}/history", headers=h["creator"]).json()
    assert any(e["event_type"] == "content.analysis_failed" for e in audit)
    assert any(e["event_type"] == "content.analysis_retried" for e in audit)
    revised = client.post(f"/api/v1/submissions/{sub}/revisions", headers=h["creator"], json={"text": "New text"})
    assert revised.status_code == 200, revised.text
    assert revised.json()["state"] == "DRAFT"


def test_m7_validates_bad_json_and_login_rate_limit(env):
    client, h, ids, auth, wf, knowledge = env
    response = client.post("/api/v1/submissions", headers=h["creator"], json={"title":"Only title"})
    assert response.status_code == 422
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"email":"unknown@invalid.demo","password":"wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email":"unknown@invalid.demo","password":"wrong"}).status_code == 429
