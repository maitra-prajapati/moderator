"""M1 contract, API, and negative tests.

"""

from backend.modules.auth.models import User

from backend.modules.auth.security import (
    hash_password,
    create_access_token,
    get_jwt_secret,
)
from copy import deepcopy
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main.main import create_app
from backend.modules.knowledge.models import knowledge_version
from backend.modules.knowledge.seed import FLOWPILOT, seed
from backend.modules.knowledge.database import make_session_factory
from backend.contracts.validate_v_1 import validate_json


def make_test_setup(tmp_path):

    url = (
        f"sqlite+pysqlite:///"
        f"{tmp_path / 'knowledge-test.sqlite'}"
    )

    app = create_app(url)

    factory = make_session_factory(url)

    seed(factory)

    with factory() as session:

        admin = User(
            email="m1-test-admin@example.com",
            password_hash=hash_password(
                "TestsOnlyPassword#123"
            ),
            role="admin",
        )

        session.add(admin)
        session.commit()

        admin_id = admin.id

    client = TestClient(app)

    token = create_access_token(
        admin_id,
        get_jwt_secret(),
    )

    client.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return client, factory

def test_seed_active_snapshot_matches_contract(tmp_path):
    client, _ = make_test_setup(tmp_path)
    response = client.get('/api/v1/brands/brand_flowpilot/knowledge')
    assert response.status_code == 200
    data = response.json()
    assert validate_json(data, 'knowledge-snapshot')['valid'] is True
    assert data['claims'][0]['value'] == 14
    assert data['rules'][0]['replacement'] == 'FlowPilot'


def test_seed_idempotent(tmp_path):
    _, factory = make_test_setup(tmp_path)
    assert seed(factory)['version_no'] == 1


def test_unknown_brand_returns_404(tmp_path):
    client, _ = make_test_setup(tmp_path)
    response = client.get('/api/v1/brands/unknown/knowledge')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'KNOWLEDGE_NOT_FOUND'
    assert validate_json(response.json(), 'api-error')['valid'] is True



def test_new_version_and_immmutable_activation(tmp_path):
    client, _ = make_test_setup(tmp_path)
    draft = deepcopy(FLOWPILOT)
    draft['voice_traits'] = ['clear', 'helpful']
    created = client.post('/api/v1/brands/brand_flowpilot/knowledge', json=draft)
    assert created.status_code == 201
    assert created.json()['version_no'] == 2
    activated = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert activated.status_code == 200
    assert activated.json()['voice_traits'] == ['clear', 'helpful']
    assert validate_json(activated.json(), 'knowledge-snapshot')['valid']
    duplicate = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert duplicate.status_code == 409
    assert client.get('/api/v1/brands/brand_flowpilot/knowledge').json()['version_no'] == 2



def test_missing_source_rejected(tmp_path):
    client, _ = make_test_setup(tmp_path)
    draft = deepcopy(FLOWPILOT)
    draft['claims'][0]['source_id'] = 'does_not_exist'
    assert client.post('/api/v1/brands/brand_flowpilot/knowledge', json=draft).status_code == 201
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_KNOWLEDGE'





def test_expired_source_rejected(tmp_path):
    client, _ = make_test_setup(tmp_path)
    draft = deepcopy(FLOWPILOT)
    draft['sources'][0]['valid_until'] = (date.today() - timedelta(days=1)).isoformat()
    assert client.post('/api/v1/brands/brand_flowpilot/knowledge', json=draft).status_code == 201
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'EXPIRED_SOURCE'


def test_duplicate_fact_key_rejected(tmp_path):
    client, _ = make_test_setup(tmp_path)
    draft = deepcopy(FLOWPILOT)
    duplicate = deepcopy(draft['claims'][0])
    duplicate['id'] = 'claim_dup'
    draft['claims'].append(duplicate)
    client.post('/api/v1/brands/brand_flowpilot/knowledge', json=draft)
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert response.status_code == 422
    assert 'fact_key' in response.json()['error']['message']


def test_invalid_request_type_rejected(tmp_path):
    client, _ = make_test_setup(tmp_path)
    draft = deepcopy(FLOWPILOT)
    draft['claims'][0]['value'] = 'fourteen'
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge', json=draft)
    assert response.status_code == 422


def test_activated_payload_not_mutated(tmp_path):
    client, factory = make_test_setup(tmp_path)
    initial = client.get('/api/v1/brands/brand_flowpilot/knowledge').json()
    client.post('/api/v1/brands/brand_flowpilot/knowledge', json=FLOWPILOT)
    after = client.get('/api/v1/brands/brand_flowpilot/knowledge').json()
    assert initial == after
    with factory() as session:
        records = session.scalars(select(knowledge_version).order_by(knowledge_version.version_no)).all()
        assert records[0].status == 'ACTIVATED'
        assert records[1].status == 'DRAFT'


def test_invalid_request_uses_shared_api_error_contract(tmp_path):
    client, _ = make_test_setup(tmp_path)
    bad = deepcopy(FLOWPILOT)
    bad['claims'][0]['value'] = 'invalid'
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge', json=bad)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_REQUEST'
    assert validate_json(response.json(), 'api-error')['valid']


def test_activate_stale_draft_rejected(tmp_path):
    client, _ = make_test_setup(tmp_path)
    assert client.post('/api/v1/brands/brand_flowpilot/knowledge', json=FLOWPILOT).status_code == 201
    assert client.post('/api/v1/brands/brand_flowpilot/knowledge', json=FLOWPILOT).status_code == 201
    assert client.post('/api/v1/brands/brand_flowpilot/knowledge/3/activate').status_code == 200
    response = client.post('/api/v1/brands/brand_flowpilot/knowledge/2/activate')
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'STALE_VERSION'