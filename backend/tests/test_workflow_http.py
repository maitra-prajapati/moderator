"""Black-box FastAPI M1/M2/M3 composition checks with signed JWTs."""
import pytest
from fastapi.testclient import TestClient
from backend.main.main import create_app
from backend.modules.knowledge.database import make_session_factory as knowledge_db
from backend.modules.knowledge.seed import seed
from backend.modules.auth.models import User
from backend.modules.auth.security import hash_password, create_access_token, get_jwt_secret
from backend.modules.workflow.database import make_session_factory as workflow_db
from backend.modules.workflow.schemas import AnalysisResponse
from backend.modules.workflow.service import complete_analysis
from backend.contracts.validate_v_1 import validate_json


@pytest.fixture
def client_db(tmp_path):
    main_url = f'sqlite+pysqlite:///{tmp_path / "brand.sqlite"}'
    workflow_url = f'sqlite+pysqlite:///{tmp_path / "workflow.sqlite"}'
    app = create_app(main_url, workflow_url)
    brand_factory = knowledge_db(main_url)
    workflow_factory = workflow_db(workflow_url)
    seed(brand_factory)
    with brand_factory() as s:
        users = {
            'creator': User(email='creator2@example.com', role='creator', password_hash=hash_password('CreatorPassword#123')),
            'reviewer': User(email='reviewer2@example.com', role='reviewer', password_hash=hash_password('ReviewerPassword#123')),
            'admin': User(email='admin2@example.com', role='admin', password_hash=hash_password('AdminPassword#123')),
        }
        s.add_all(users.values())
        s.commit()
        ids = {name: user.id for name, user in users.items()}
    return TestClient(app), workflow_factory, ids


def auth(ids, name):
    return {'Authorization': 'Bearer ' + create_access_token(ids[name], get_jwt_secret())}


def draft():
    return {'brand_id': 'brand_flowpilot', 'title': 'Landing copy',
            'channel': 'linkedin', 'text': 'Flow Pilot offers 30-day trial.'}


def make_submission(client, ids):
    return client.post('/api/v1/submissions', json=draft(), headers=auth(ids,'creator'))


def complete(flow_db, payload, findings=None):
    with flow_db() as session:
        return complete_analysis(session, AnalysisResponse(
            request_id=payload['request_id'], submission_id=payload['submission_id'],
            revision_id=payload['current_revision_id'], findings=findings or []))


def test_public_routes_require_auth(client_db):
    client, _, _ = client_db
    for method, endpoint, json in [
        ('post', '/api/v1/submissions', draft()),
        ('get', '/api/v1/submissions', None),
        ('get', '/api/v1/submissions/sub_nonexistent', None),
    ]:
        assert (client.post(endpoint, json=json) if method == 'post' else client.get(endpoint)).status_code == 401


def test_creator_draft_submits_and_reviewer_approves_clean_fixture(client_db):
    client, flow_db, ids = client_db
    c = auth(ids, 'creator')
    r = auth(ids, 'reviewer')
    created = make_submission(client, ids)
    assert created.status_code == 201, created.text
    body = created.json()
    assert validate_json(body, 'workflow-submission')['valid']
    sub_id = body['submission_id']
    assert client.get(f'/api/v1/submissions/{sub_id}', headers=c).json()['text'] == draft()['text']
    assert len(client.get('/api/v1/submissions', headers=r).json()) == 1
    submitted = client.post(f'/api/v1/submissions/{sub_id}/submit', headers=c)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['state'] == 'ANALYZING'
    assert submitted.json()['knowledge_version_id'].startswith('kv_')
    assert submitted.json()['request_id']
    assert client.post(f'/api/v1/submissions/{sub_id}/reviews',
                       json={'decision': 'approve','comment': ''}, headers=r).status_code == 409
    complete(flow_db, submitted.json())
    approved = client.post(f'/api/v1/submissions/{sub_id}/reviews',
                           json={'decision': 'approve','comment': 'Reviewed clean fixture'}, headers=r)
    assert approved.status_code == 200, approved.text
    assert approved.json()['state'] == 'APPROVED'
    assert client.post(f'/api/v1/submissions/{sub_id}/reviews',
                       json={'decision': 'approve','comment': 'Reviewed clean fixture'}, headers=r).status_code == 200
    events = client.get(f'/api/v1/submissions/{sub_id}/history', headers=c).json()
    assert len([e for e in events if e['event_type']=='review.approved']) == 1


def test_no_self_approval_and_creator_cannot_manage_others(client_db):
    client, flow_db, ids = client_db
    created = make_submission(client, ids).json()
    sub = created['submission_id']
    sent = client.post(f'/api/v1/submissions/{sub}/submit', headers=auth(ids,'creator')).json()
    complete(flow_db, sent)
    assert client.post(f'/api/v1/submissions/{sub}/reviews',
                       json={'decision': 'approve','comment': ''}, headers=auth(ids,'creator')).status_code == 403
    assert client.post('/api/v1/submissions', json=draft(), headers=auth(ids,'reviewer')).status_code == 403


def test_version_does_not_change_when_submit_repeated(client_db):
    client, _, ids = client_db
    created = make_submission(client, ids).json()
    path = f"/api/v1/submissions/{created['submission_id']}/submit"
    first = client.post(path, headers=auth(ids,'creator')).json()
    second = client.post(path, headers=auth(ids,'creator')).json()
    assert first['request_id'] == second['request_id']
    assert first['knowledge_version_id'] == second['knowledge_version_id']


def test_invalid_payload_and_unauthorized_access(client_db):
    client, _, ids = client_db
    assert client.post('/api/v1/submissions', json={'title':'only'},
                       headers=auth(ids,'creator')).status_code == 422
    assert client.get('/api/v1/submissions/does-not-exist',
                      headers=auth(ids,'creator')).status_code == 404
    created = make_submission(client, ids).json()
    assert client.post(f"/api/v1/submissions/{created['submission_id']}/revisions",
                       json={'text': 'Modified'}, headers=auth(ids,'reviewer')).status_code == 403


def test_unknown_knowledge_version_cannot_submit(client_db):
    client, _, ids = client_db
    body = draft()
    body['brand_id'] = 'brand_unknown'
    created = client.post('/api/v1/submissions', json=body, headers=auth(ids,'creator')).json()
    response = client.post(f"/api/v1/submissions/{created['submission_id']}/submit",
                           headers=auth(ids,'creator'))
    assert response.status_code == 404