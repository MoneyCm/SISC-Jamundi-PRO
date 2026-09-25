"""Compromisos del Consejo de Seguridad: importación, seguimiento y lectura para la sesión."""
from datetime import date

import pytest

from db.models_council import CouncilCommitment
from services import council_commitments_service as svc

SHEET = [
    ["SEGUIMIENTO DE COMPROMISOS", "", ""],
    ["ID", "Fecha origen", "Acta origen", "Compromiso consolidado", "Responsable principal", "Plazo textual",
     "Fecha límite", "Tema", "Menciones", "Última mención"],
    ["CS-2026-001", "14/01/2026", "Acta 01", "Convocar reunión de seguimiento", "Secretaría de Seguridad",
     "15/01/2026", "15/01/2026", "Gestión institucional", "1", "14/01/2026"],
    ["CS-2026-018", "23/02/2026", "Acta 11", "Presentar informe mensual de las cámaras", "Policía Nacional",
     "Mensual", "", "Videovigilancia y tecnología", "5", "25/06/2026"],
    ["", "", "", "", "", "", "", "", "", ""],
    ["Otra tabla", "", "", "", "", "", "", "", "", ""],
]


class FakeQuery:
    def __init__(self, rows):
        self.rows, self._code = rows, None

    def filter(self, condition):
        self._code = condition.right.value
        return self

    def with_for_update(self):
        return self

    def first(self):
        return next((row for row in self.rows if row.code == self._code), None)

    def all(self):
        return list(self.rows)


class FakeSession:
    """Sesión mínima en memoria para probar la lógica sin base de datos."""

    def __init__(self):
        self.rows, self.updates = [], []

    def query(self, model):
        return FakeQuery(self.rows if model is CouncilCommitment else self.updates)

    def add(self, obj):
        (self.rows if isinstance(obj, CouncilCommitment) else self.updates).append(obj)

    def flush(self):
        for row in self.rows:
            if row.id is None:
                import uuid
                row.id = uuid.uuid4()

    def commit(self):
        self.flush()

    def refresh(self, obj):
        pass


def test_sheet_is_parsed_and_stops_at_the_end_of_the_table():
    items = svc.rows_from_table(SHEET)
    assert [item["code"] for item in items] == ["CS-2026-001", "CS-2026-018"]
    assert items[0]["deadline_date"] == date(2026, 1, 15)
    assert items[1]["deadline_date"] is None and items[1]["mentions"] == 5


def test_import_is_idempotent_and_never_overwrites_followup_status():
    db = FakeSession()
    assert svc.import_commitments(db, svc.rows_from_table(SHEET), "importador")["created"] == 2
    row = next(r for r in db.rows if r.code == "CS-2026-018")
    svc.update_status(db, "CS-2026-018", status="EN_CURSO", note="Policía envió borrador", evidence_url=None,
                      deadline_date=date(2026, 10, 30), expected_version=row.version, username="analista")
    result = svc.import_commitments(db, svc.rows_from_table(SHEET), "importador")
    assert result == {"created": 0, "updated": 0, "unchanged": 2, "total": 2}
    assert row.status == "EN_CURSO" and row.validated == "VALIDADO"


def test_closing_requires_support_and_stale_versions_are_rejected():
    db = FakeSession()
    svc.import_commitments(db, svc.rows_from_table(SHEET), "importador")
    row = next(r for r in db.rows if r.code == "CS-2026-001")
    with pytest.raises(ValueError, match="cómo se verificó"):
        svc.update_status(db, "CS-2026-001", status="CUMPLIDO", note="", evidence_url=None,
                          deadline_date=None, expected_version=row.version, username="analista")
    with pytest.raises(PermissionError):
        svc.update_status(db, "CS-2026-001", status="EN_CURSO", note=None, evidence_url=None,
                          deadline_date=None, expected_version=row.version + 5, username="analista")


def test_flags_and_agenda_put_repeated_commitments_first():
    db = FakeSession()
    svc.import_commitments(db, svc.rows_from_table(SHEET), "importador")
    today = date(2026, 9, 24)
    by_code = {row.code: svc.serialize(row, today) for row in db.rows}
    assert "ATRASADO" in by_code["CS-2026-001"]["flags"]
    assert {"REPETIDO", "SIN_FECHA", "SIN_INFORMACION"} <= set(by_code["CS-2026-018"]["flags"])
    text = svc.agenda_text(db.rows, today)
    assert text.index("CS-2026-018") < text.index("CS-2026-001")
    assert "pedido 5 veces" in text and "no tienen fecha límite" in text
    summary = svc.summary(db.rows, today)
    assert summary["repeated"] == 1 and summary["overdue"] == 1 and summary["without_information"] == 2


@pytest.mark.parametrize("url", ["javascript:alert(document.cookie)", "data:text/html,<script>x</script>", "drive.google.com/x"])
def test_evidence_link_must_be_a_web_address(url):
    db = FakeSession()
    svc.import_commitments(db, svc.rows_from_table(SHEET), "importador")
    row = next(r for r in db.rows if r.code == "CS-2026-001")
    with pytest.raises(ValueError, match="https://"):
        svc.update_status(db, "CS-2026-001", status="CUMPLIDO", note=None, evidence_url=url,
                          deadline_date=None, expected_version=row.version, username="analista")


def test_short_title_before_colon_is_ignored_when_matching():
    assert svc._matching_text("Podar árboles: Realizar la poda de árboles en Zanjón") == " Realizar la poda de árboles en Zanjón"
    assert svc._matching_text("Oficio: corto") == "Oficio: corto"
    long_head = "La Secretaría de Seguridad y Convivencia informó en la sesión: que se hará el operativo"
    assert svc._matching_text(long_head) == long_head


def test_recurrence_counts_sessions_once_and_keeps_history_out_of_open_commitments():
    from datetime import date as d
    from types import SimpleNamespace as NS

    from services.council_topics import theme_for, topics_in

    history = [
        NS(id="h1", instance="PLANEACION_SEMANAL", act_date=d(2025, 3, 6), status="HISTORICA",
           reading={"topics": {"caravanas": 3, "motos": 1}, "proposals": [], "warnings": []}),
        # Mismo día y misma instancia en otro archivo: es la misma sesión.
        NS(id="h2", instance="PLANEACION_SEMANAL", act_date=d(2025, 3, 6), status="HISTORICA",
           reading={"topics": {"caravanas": 2}, "proposals": [], "warnings": []}),
        NS(id="h3", instance="PLANEACION_SEMANAL", act_date=d(2024, 12, 5), status="HISTORICA",
           reading={"topics": {}, "proposals": [{"text": "Programar caravanas de seguridad los fines de semana"}], "warnings": []}),
    ]
    open_row = NS(code="CS-2026-049", instance="CONSEJO_SEGURIDAD", origin_date=d(2026, 6, 25), status="SIN_INFORMACION",
                  text="Reactivar las caravanas de seguridad", mentions=2)
    closed_row = NS(code="CS-2026-001", instance="CONSEJO_SEGURIDAD", origin_date=d(2026, 1, 14), status="CUMPLIDO",
                    text="Caravana especial de enero", mentions=1)
    result = svc.recurrence(None, reads=history, commitments=[open_row, closed_row])
    caravanas = next(topic for topic in result["topics"] if topic["key"] == "caravanas")
    assert caravanas["years"] == {"2024": 1, "2025": 1, "2026": 2}
    assert caravanas["first_date"] == "2024-12-05"
    assert caravanas["open_codes"] == ["CS-2026-049"]  # lo histórico y lo cumplido no cuentan como abierto
    assert "motos" not in {topic["key"] for topic in result["topics"]}  # una mención de paso no es tema
    assert topics_in("Instalar cámaras en el parque") == ["camaras"]
    assert theme_for("Censo de damnificados por el desplazamiento") == "Protección y derechos humanos"


def test_historical_reads_cannot_be_confirmed():
    from types import SimpleNamespace as NS

    record = NS(status="HISTORICA", reading={"proposals": []})

    class Query:
        def filter(self, *args):
            return self

        def with_for_update(self):
            return self

        def first(self):
            return record

    class Db:
        def query(self, model):
            return Query()

    with pytest.raises(PermissionError, match="históricas"):
        svc.confirm_act(Db(), "00000000-0000-0000-0000-000000000001", [], [], "analista")
