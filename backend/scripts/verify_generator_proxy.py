"""Local-only acceptance of login, upload, quality blocking, reuse and calculation.

Uses a synthetic workbook prepared in staging. Password supplied through environment,
never logged. Does not publish. Run --help for inputs.
"""
import argparse
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://127.0.0.1:3100')
parser.add_argument('--username', required=True)
parser.add_argument('--password-env', default='SISC_TEST_PASSWORD')
parser.add_argument('--file', required=True)
args = parser.parse_args()
assert urlparse(args.base).hostname in {'127.0.0.1', 'localhost'}
base = args.base.rstrip('/')
file = Path(args.file)
with httpx.Client(base_url=base, timeout=90) as c:
    assert c.get('/api/generator/session').json()['authenticated'] is False
    assert c.post('/api/generator/ingestion/upload').status_code == 401
    assert c.post('/api/generator/session', headers={'Origin': 'https://example.org'}, json={}).status_code == 403
    assert c.post('/api/generator/session', json={'username': args.username, 'password': 'invalid-test-password'}).status_code == 401
    login = c.post('/api/generator/session', json={'username': args.username, 'password': os.environ[args.password_env]})
    assert login.status_code == 200
    assert 'httponly' in login.headers['set-cookie'].lower() and 'samesite=strict' in login.headers['set-cookie'].lower()
    assert 'access_token' not in login.json()
    assert c.get('/api/generator/session').json()['authenticated'] is True
    bad = c.post('/api/generator/ingestion/preflight', files={'file': ('invalid.csv', b'wrong\nvalue\n', 'text/csv')})
    assert bad.status_code == 200 and bad.json()['status'] == 'BLOCKED'
    bad_gate = c.post('/api/generator/ingestion/upload', files={'file': ('invalid.csv', b'wrong\nvalue\n', 'text/csv')})
    assert bad_gate.status_code == 422
    content = file.read_bytes()
    def upload(operation):
        return c.post('/api/generator/ingestion/' + operation, files={'file': (file.name, content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    preflight = upload('preflight')
    assert preflight.status_code == 200 and preflight.json()['status'] != 'BLOCKED'
    accepted = upload('upload')
    assert accepted.status_code == 200, accepted.text
    run_id = accepted.json()['ingestion_id']
    for _ in range(100):
        run = c.get('/api/generator/ingestion/' + run_id).json()
        if run['status'] == 'COMPLETED': break
        assert run['status'] != 'FAILED'
        time.sleep(1)
    assert run['status'] == 'COMPLETED' and run['rechazadas'] == 0
    again = upload('upload').json()
    assert again['status'] == 'skipped' and again['ingestion_id'] == run_id
    result = c.post('/api/official-indicator', json={'indicator': 'SEGURIDAD_TOTAL', 'period': {'start': '2026-07-01', 'end': '2026-07-05'},
        'territory': 'JAMUNDI', 'source_version_id': run_id, 'methodology_version': '1'})
    assert result.status_code == 200 and result.json()['value'] == 2
    summary = c.get('/api/generator/summary/' + run_id)
    assert summary.status_code == 200 and summary.json().get('note')
    assert c.delete('/api/generator/session').status_code == 200
    assert c.get('/api/generator/ingestion/' + run_id).status_code == 401
    print('PASS: session, HttpOnly cookie, CSRF, denied login, invalid file, gate, completed upload, idempotency, official=2, historical check, logout')
    print('Synthetic staging delivery:', run_id)
