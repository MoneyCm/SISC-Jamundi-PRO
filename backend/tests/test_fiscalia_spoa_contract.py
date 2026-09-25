import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import fiscalia_spoa, source_center
from db.models_fiscalia_spoa import FiscaliaSpoaRecord, FiscaliaSpoaSnapshot


def test_spoa_dataset_contract_and_record_key_are_stable():
    assert {item["id"] for item in fiscalia_spoa.DATASET_CONFIG.values()} == {
        "dbdv-iihs", "hr73-zqjf", "piva-db2c"
    }
    config = fiscalia_spoa.DATASET_CONFIG["procesos"]
    row = {"proceso_anonimizado": "opaque", "deli_id": "10"}
    assert fiscalia_spoa._record_key(row, config) == fiscalia_spoa._record_key(dict(row), config)
    assert len(fiscalia_spoa._record_key(row, config)) == 64
    assert any(item.name == "uq_spoa_snapshot_record" for item in FiscaliaSpoaRecord.__table__.constraints)
    assert any(item.name == "uq_spoa_snapshot_version" for item in FiscaliaSpoaSnapshot.__table__.constraints)


def test_spoa_ingest_payload_rejects_wrong_dataset_or_oversized_batch():
    base = {
        "run_id": "spoa-20260828-test",
        "dataset_key": "desconocido",
        "dataset_id": "dbdv-iihs",
        "cutoff_date": "2026-07-31",
        "metadata_sha256": "a" * 64,
        "payload_sha256": "b" * 64,
        "schema_version": "12345678",
        "rows": [{"x": 1}],
    }
    with pytest.raises(ValueError):
        fiscalia_spoa.SpoaIngestBatch(**base)


def test_spoa_oidc_claims_are_scoped_to_expected_repository():
    claims = {
        "repository": "MoneyCm/monitor-fiscalia-spoa-v3",
        "workflow_ref": "MoneyCm/monitor-fiscalia-spoa-v3/.github/workflows/monitor_spoa_v3.yml@refs/heads/main",
        "ref": "refs/heads/main",
        "event_name": "schedule",
        "runner_environment": "github-hosted",
    }
    source_center._validate_github_claims(claims, "FISCALIA_SPOA_V3")
    with pytest.raises(HTTPException):
        source_center._validate_github_claims({**claims, "repository": "attacker/repo"}, "FISCALIA_SPOA_V3")
