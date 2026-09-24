from datetime import datetime, timedelta, timezone
import io
import json
from types import SimpleNamespace
import zipfile
import subprocess
from unittest.mock import patch

import pytest

from scripts.sync_source_monitors import artifact_payload, evidence_for_run, should_apply, gh_api


def test_github_read_retries_transient_failure():
    success = SimpleNamespace(stdout=b'{"ok":true}')
    with patch('scripts.sync_source_monitors.subprocess.run', side_effect=[subprocess.CalledProcessError(1, 'gh'), success]) as run, patch('scripts.sync_source_monitors.time.sleep'):
        assert gh_api('repos/example/test') == {'ok': True}
        assert run.call_count == 2


def archive(payload, filename='sisc-heartbeat.json'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as bundle:
        bundle.writestr(filename, json.dumps(payload))
    return stream.getvalue()


def test_rejects_cross_connector_and_archive_paths():
    payload = {'connector_code': 'MINDEFENSA', 'last_checked_at': '2026-01-01T00:00:00Z'}
    with pytest.raises(ValueError):
        artifact_payload(archive(payload), 'SIEDCO_PUBLICO')
    with pytest.raises(ValueError):
        artifact_payload(archive(payload, '../sisc-heartbeat.json'), 'MINDEFENSA')


def test_parses_real_report_and_rejects_future_time():
    payload = {'connector_code': 'MINDEFENSA', 'last_checked_at': '2026-01-01T00:00:00Z',
               'source_cutoff_date': '2025-12-31', 'record_count': 42}
    parsed = artifact_payload(archive(payload), 'MINDEFENSA')
    assert parsed['source_cutoff_date'].isoformat() == '2025-12-31'
    assert parsed['record_count'] == 42
    payload['last_checked_at'] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError):
        artifact_payload(archive(payload), 'MINDEFENSA')


def test_workflow_success_never_fabricates_source_review(monkeypatch):
    monkeypatch.setattr('scripts.sync_source_monitors.gh_api', lambda *a, **k: {'artifacts': []})
    run = {'id': 12, 'updated_at': '2026-01-02T00:00:00Z', 'conclusion': 'success',
           'html_url': 'https://github.com/example/run/12'}
    payload = evidence_for_run('example/repo', 'MINDEFENSA', run)
    assert payload['status'] == 'NEEDS_REVIEW'
    assert 'last_checked_at' not in payload
    assert 'last_success_at' not in payload
    assert 'source_cutoff_date' not in payload
    existing = SimpleNamespace(details={}, last_checked_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert not should_apply(existing, payload)


def test_idempotency_and_older_reports():
    details = {'github_run_id': 12, 'github_run_attempt': 1, 'sync_mode': 'heartbeat_artifact'}
    existing = SimpleNamespace(details=details, last_checked_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    payload = {'details': details, 'last_checked_at': datetime(2026, 1, 1, tzinfo=timezone.utc)}
    assert not should_apply(existing, payload)
    payload['details'] = {**details, 'github_run_id': 13}
    assert not should_apply(existing, payload)
    payload['last_checked_at'] = datetime(2026, 1, 3, tzinfo=timezone.utc)
    assert should_apply(existing, payload)
