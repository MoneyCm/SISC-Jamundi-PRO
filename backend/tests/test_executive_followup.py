from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api import sisc_cifras as api
from api.auth import get_current_user


def client_for(user=None):
    app = FastAPI()
    app.include_router(api.router)
    db = MagicMock()
    query = db.query.return_value.filter.return_value
    query.count.return_value = 1
    query.order_by.return_value.limit.return_value.all.return_value = [SimpleNamespace(
        id='case-id', status='BORRADOR', document={'recommendation':'Revisar en comité',
            'problem':'Sensitive narrative excluded', 'alert_snapshot':{'secret':'excluded'}, 'evidence':[]})]
    app.dependency_overrides[api.get_db] = lambda: db
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize('user,expected', [(None,401), (SimpleNamespace(data_level_max=1,roles=[]),403)])
def test_institutional_snapshot_denies_public_access(user, expected):
    assert client_for(user).get('/executive-followup').status_code == expected


def test_snapshot_projects_only_followup_fields():
    response = client_for(SimpleNamespace(data_level_max=2,roles=[])).get('/executive-followup')
    assert response.status_code == 200
    payload = response.json()
    assert 'checked_at' in payload
    assert 'Sensitive narrative' not in response.text
    assert 'alert_snapshot' not in response.text
    assert payload['groups']['decisions']['items'][0]['recommendation'] == 'Revisar en comité'
