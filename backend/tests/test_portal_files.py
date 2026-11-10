"""El backend publico baja de Neon los archivos de metas del PISCC."""
import json

from core import public_mode


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar, self._rows = scalar, rows or []

    def scalar(self):
        return self._scalar

    def fetchall(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows, table_exists=True):
        self.rows, self.table_exists = rows, table_exists

    def execute(self, statement):
        sql = str(statement)
        if "to_regclass" in sql:
            return _Result(scalar="portal_archivos" if self.table_exists else None)
        return _Result(rows=self.rows)

    def close(self):
        pass


def test_writes_changed_files_and_ignores_unknown_or_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(public_mode, "PORTAL_FILES_DIR", tmp_path)
    good = json.dumps({"corte": "2026-09-30"})
    rows = [("historico.json", good), ("otro.json", good), ("mindefensa.json", "{no es json")]
    changed = public_mode.sync_portal_files(lambda: _FakeSession(rows))
    assert changed == ["historico.json"]
    assert (tmp_path / "historico.json").read_text(encoding="utf-8") == good
    assert not (tmp_path / "otro.json").exists()
    assert not (tmp_path / "mindefensa.json").exists()
    # Sin cambios, no reescribe.
    assert public_mode.sync_portal_files(lambda: _FakeSession(rows)) == []


def test_without_table_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(public_mode, "PORTAL_FILES_DIR", tmp_path)
    assert public_mode.sync_portal_files(lambda: _FakeSession([], table_exists=False)) == []
