import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.asistente_compromisos import resumir
from services.asistente_secretaria import responder


def row(code, mentions, deadline, **changes):
    return SimpleNamespace(**dict(dict(code=code, text='Tarea de prueba', responsible='Dependencia',
        status='PENDIENTE', mentions=mentions, deadline_date=deadline, origin_act='Acta de prueba',
        instance='CONSEJO_SEGURIDAD', kind='COMPROMISO'), **changes))


def test_most_requested_without_deadline_comes_first():
    rows = [row('CS-1', 1, date(2026, 1, 15), origin_act='Acta 01'),
            row('CS-CAM', 6, None, text='Informe de cámaras', responsible='Policía Nacional'),
            row('COP-1', 99, date(2026, 1, 1), instance='COMITE_ORDEN_PUBLICO'),
            row('CS-CLOSED', 99, date(2026, 1, 1), status='NO_CUMPLIDO')]
    text = resumir(rows, date(2026, 9, 30))
    assert text.index('CS-CAM:') < text.index('CS-1:')
    assert 'Informe de cámaras' in text and 'Pedido 6 veces' in text
    assert 'Sin fecha límite registrada' in text and 'Policía Nacional' in text
    assert 'COP-1:' not in text and 'CS-CLOSED:' not in text
    assert '258 días de atraso' in text


def test_ties_are_one_summary_without_individual_list():
    rows = [row(f'CS-{i}', 1, date(2026, 1, 15), origin_act='Acta 01') for i in range(25)]
    rows.append(row('CS-CAM', 6, None))
    text = resumir(rows, date(2026, 9, 30))
    assert '25 compromisos del Acta 01 siguen abiertos con plazo vencido el 15 de enero de 2026' in text
    assert 'CS-0:' not in text and 'CS-24:' not in text
    assert 'empatados' not in text


def test_no_deadline_is_not_treated_as_overdue_and_closed_rows_are_excluded():
    text = resumir([row('CS-1', 6, None), row('CS-2', 99, date(2026, 1, 1), status='CUMPLIDO')], date(2026, 9, 30))
    assert 'CS-1:' in text and 'No hay compromisos abiertos con fecha límite vencida' in text
    assert 'CS-2:' not in text
    assert 'No hay compromisos abiertos' in resumir([], date(2026, 9, 30))


def test_delay_question_prioritizes_delay():
    rows = [row('CS-OLD', 1, date(2026, 1, 1)), row('CS-REPEAT', 6, None)]
    text = resumir(rows, date(2026, 9, 30), por_atraso=True)
    assert text.index('CS-OLD:') < text.index('CS-REPEAT:')


def test_exact_user_question_does_not_need_police_or_ai(monkeypatch):
    from services import asistente_secretaria as svc
    def unexpected(*args):
        raise AssertionError('Must not load police data')
    monkeypatch.setattr(svc, 'construir_expediente', unexpected)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [row('CS-1', 4, date(2026, 8, 1))]
    result = asyncio.run(responder(db, 'Cual es el compromiso mas incumplido de los concejos de seguridad', hoy=date(2026, 9, 30)))
    assert 'CS-1:' in result['respuesta']
    assert '30 de septiembre de 2026' in result['respuesta']
    assert 'policial' not in result['respuesta'].lower()


def test_general_commitment_question_does_not_load_police(monkeypatch):
    from services import asistente_secretaria as svc
    def unexpected(*args):
        raise AssertionError('Police data must not be consulted')
    monkeypatch.setattr(svc, 'construir_expediente', unexpected)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [row('CS-1', 6, None)]
    result = asyncio.run(responder(db, '¿Qué compromisos tiene la Policía?', hoy=date(2026, 9, 30)))
    assert 'sábana' not in result['respuesta'].lower()
    assert 'Secretaría Técnica' not in result['respuesta']
    assert all('Policía al' not in source for source in result['fuentes'])


def test_list_of_overdue_commitments_for_an_entity():
    from services.asistente_compromisos import listar
    rows = [row('CS-NEW', 1, date(2026, 9, 1)), row('CS-OLD', 1, date(2026, 1, 15)),
            row('CS-OPEN', 6, None), row('CS-FUT', 2, date(2026, 12, 1))]
    texto = listar(rows, date(2026, 9, 30), 'la Policía', solo_vencidos=True)
    assert texto.startswith('La Policía tiene 4 compromisos abiertos del Consejo de Seguridad; 2 con el plazo vencido.')
    assert texto.index('CS-OLD:') < texto.index('CS-NEW:')
    assert 'CS-OPEN' not in texto and 'CS-FUT' not in texto
    assert 'pedido 1 vez;' in texto and '258 días de atraso' in texto
    todos = listar(rows, date(2026, 9, 30), 'la Policía')
    assert 'CS-OPEN' in todos and 'sin fecha límite registrada' in todos


def test_police_question_lists_only_police_commitments():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        row('CS-POL', 1, date(2026, 1, 15), responsible='Policía Nacional'),
        row('CS-SEC', 1, date(2026, 1, 15), responsible='Secretaría de Seguridad y Convivencia')]
    result = asyncio.run(responder(db, '¿Qué compromisos tiene vencidos la Policía?', hoy=date(2026, 9, 30)))
    assert 'CS-POL' in result['respuesta'] and 'CS-SEC' not in result['respuesta']
