import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from api.asistente import Pregunta
from api import ia
from services import asistente_secretaria as svc


def test_specific_theft_does_not_expand_to_other_crimes():
    db = MagicMock()
    db.query.return_value.filter.return_value.distinct.return_value = []
    for question in ['¿Cuántos hurtos a personas hubo?', '¿Cómo va el hurto a personas?', '¿Y los robos a personas?']:
        assert svc.detectar_temas(db, question)['delitos'] == ['Hurto a personas']
    assert len(svc.detectar_temas(db, '¿Cuántos hurtos hubo?')['delitos']) == 5


def test_verified_selection_keeps_indicator_counts_and_direction_together():
    exp = svc.Expediente()
    exp.agregar('Policía', ['Homicidios: 2 esta semana y 3 la anterior (bajó en 1).', 'Hurtos: 20.'])
    for text in ['Esta semana hubo 20 homicidios.', 'Los homicidios subieron de 3 a 2.',
                 'Policía: Homicidios: 20 esta semana y 3 la anterior (bajó en 1).']:
        assert not svc.verificar_seleccion(text, exp)
    assert svc.verificar_seleccion('• Policía: Homicidios: 2 esta semana y 3 la anterior (bajó en 1).', exp)


def test_piscc_without_ai_uses_goals_not_general_summary():
    exp = svc.Expediente()
    exp.agregar('Cifras generales', ['Homicidios: 2'])
    exp.agregar('Metas del PISCC 2024-2027 (tabla 16)', ['Meta: en riesgo'])
    text = svc.respuesta_sin_ia('¿Cómo va el PISCC?', exp, {'datos': {'frases': ['Resumen general']}})
    assert 'Meta: en riesgo' in text and 'Resumen general' not in text


@pytest.mark.parametrize('question', ['¿Qué pasó ayer?', 'Del 01/02 al 28/02', 'Los últimos 30 días', 'Homicidios entre enero y marzo'])
def test_requested_dates_are_not_silently_replaced(question, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('Must not query a different period')
    monkeypatch.setattr(svc, 'construir_expediente', unexpected)
    result = asyncio.run(svc.responder(None, question))
    assert 'rango de fechas' in result['respuesta'] and result['verificada'] is False


def test_default_periods_and_plan_name_remain_supported():
    for question in ['¿Cómo vamos esta semana?', '¿Cómo va la convivencia este año?', '¿Cómo va el PISCC 2024-2027?']:
        assert not svc.periodo_no_soportado(question)
    with pytest.raises(ValidationError):
        Pregunta(pregunta='   ')


def test_provider_wrong_attribution_falls_back(monkeypatch):
    exp = svc.Expediente()
    exp.agregar('Policía', ['Homicidios: 2.', 'Hurtos: 20.'])
    extra = {'datos': {'frases': ['Homicidios: 2.'], 'corte': date(2026, 9, 1)}}
    monkeypatch.setattr(svc, 'construir_expediente', lambda *args: (exp, extra))
    monkeypatch.setattr(ia, 'GEMINI_API_KEY', 'test')
    monkeypatch.setattr(ia, 'MISTRAL_API_KEY', None)
    async def wrong(_):
        return 'Esta semana hubo 20 homicidios.'
    monkeypatch.setattr(ia, 'call_gemini', wrong)
    result = asyncio.run(svc.responder(None, '¿Cómo vamos?'))
    assert result['redactada_por'] == 'SISC (sin IA)'
    assert '20 homicidios' not in result['respuesta']
    assert 'Corte policial' in result['respuesta']


def test_single_month_is_parsed_and_ranges_are_not():
    hoy = date(2026, 9, 30)
    assert svc.periodo_mes('¿Cuántos homicidios hubo en agosto?', hoy) == (date(2026, 8, 1), date(2026, 8, 31))
    assert svc.periodo_mes('Homicidios en enero de 2025', hoy) == (date(2025, 1, 1), date(2025, 1, 31))
    assert svc.periodo_mes('¿Y en diciembre?', hoy) == (date(2025, 12, 1), date(2025, 12, 31))
    assert svc.periodo_mes('Hurtos el mes pasado', hoy) == (date(2026, 8, 1), date(2026, 8, 31))
    assert svc.periodo_mes('Homicidios entre enero y marzo', hoy) is None
    assert svc.periodo_mes('¿Cuál es el barrio mayor?', hoy) is None


def test_crimes_outside_the_weekly_sheet_use_the_piscc_indicator():
    db = MagicMock()
    db.query.return_value.filter.return_value.distinct.return_value = []
    assert svc.detectar_temas(db, '¿Qué pasa con la extorsión?')['piscc'] == ['extorsion']
    assert svc.detectar_temas(db, '¿Cómo va la violencia intrafamiliar?')['piscc'] == ['vif']
    assert svc.detectar_temas(db, '¿Cuántos secuestros van?')['piscc'] == ['secuestro']
    assert svc.detectar_temas(db, '¿Cómo van los homicidios?')['piscc'] == []


def test_selected_lines_show_each_title_once():
    exp = svc.Expediente()
    exp.agregar('Barrio Terranova', ['Últimas cuatro semanas: 9 casos.', 'En el año: 63 casos.'])
    exp.agregar('Barrio', ['Otro: 1.'])
    texto = svc.formatear_seleccion('Barrio Terranova: Últimas cuatro semanas: 9 casos.\n'
                                    '• Barrio Terranova: En el año: 63 casos.', exp)
    assert texto == 'Barrio Terranova:\n• Últimas cuatro semanas: 9 casos.\n• En el año: 63 casos.'
    assert svc.veces(1) == '1 vez' and svc.veces(6) == '6 veces'
