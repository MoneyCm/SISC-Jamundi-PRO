from datetime import date

import pytest

from services.asistente_periodos import meses_de, periodo

HOY = date(2026, 9, 30)


@pytest.mark.parametrize('pregunta, inicio, fin, etiqueta', [
    ('¿Cuántos homicidios hubo en agosto?', date(2026, 8, 1), date(2026, 8, 31), 'agosto de 2026'),
    ('Homicidios en enero de 2025', date(2025, 1, 1), date(2025, 1, 31), 'enero de 2025'),
    ('¿Y en diciembre?', date(2025, 12, 1), date(2025, 12, 31), 'diciembre de 2025'),
    ('Hurtos el mes pasado', date(2026, 8, 1), date(2026, 8, 31), 'agosto de 2026'),
    ('Agosto del año pasado', date(2025, 8, 1), date(2025, 8, 31), 'agosto de 2025'),
    ('Homicidios en agosto del año antepasado', date(2024, 8, 1), date(2024, 8, 31), 'agosto de 2024'),
    ('Diciembre de este año', date(2026, 12, 1), date(2026, 12, 31), 'diciembre de 2026'),
    ('Del 5 al 10 de agosto de 2025', date(2025, 8, 5), date(2025, 8, 10), 'del 5 al 10 de agosto de 2025'),
    ('Hurtos el 5 de agosto', date(2026, 8, 5), date(2026, 8, 5), 'el 5 de agosto de 2026'),
    ('Del 5 de julio al 10 de agosto', date(2026, 7, 5), date(2026, 8, 10), 'del 5 de julio al 10 de agosto de 2026'),
    ('Del 20 de diciembre al 10 de enero', date(2025, 12, 20), date(2026, 1, 10),
     'del 20 de diciembre de 2025 al 10 de enero de 2026'),
    ('Primera semana de agosto', date(2026, 8, 1), date(2026, 8, 7), 'del 1 al 7 de agosto de 2026'),
    ('Última semana de agosto', date(2026, 8, 25), date(2026, 8, 31), 'del 25 al 31 de agosto de 2026'),
    ('Segunda quincena de julio', date(2026, 7, 16), date(2026, 7, 31), 'del 16 al 31 de julio de 2026'),
    ('Homicidios entre enero y marzo', date(2026, 1, 1), date(2026, 3, 31), 'de enero a marzo de 2026'),
    ('De noviembre a febrero', date(2025, 11, 1), date(2026, 2, 28), 'de noviembre de 2025 a febrero de 2026'),
    ('Del 01/08 al 15/08/2025', date(2025, 8, 1), date(2025, 8, 15), 'del 1 al 15 de agosto de 2025'),
    ('¿Qué pasó ayer?', date(2026, 9, 29), date(2026, 9, 29), 'el 29 de septiembre de 2026'),
    ('Los últimos 10 días', date(2026, 9, 21), date(2026, 9, 30), 'del 21 al 30 de septiembre de 2026'),
    ('La semana pasada', date(2026, 9, 21), date(2026, 9, 27), 'del 21 al 27 de septiembre de 2026'),
])
def test_periodos_entendidos(pregunta, inicio, fin, etiqueta):
    resultado = periodo(pregunta, HOY)
    assert (resultado.inicio, resultado.fin, resultado.etiqueta) == (inicio, fin, etiqueta)


@pytest.mark.parametrize('pregunta', ['¿Cómo vamos esta semana?', '¿Cómo va el PISCC 2024-2027?', '¿Cuál es el barrio mayor?',
                                      'Los primeros días de agosto', '31 de febrero', 'Hurtos del 5, 6 y 7 de agosto',
                                      'Tercera quincena de agosto'])
def test_sin_periodo_claro_no_se_adivina(pregunta):
    assert periodo(pregunta, HOY) is None


def test_meses_de_un_periodo():
    assert meses_de(date(2025, 12, 20), date(2026, 1, 10)) == [(date(2025, 12, 20), date(2025, 12, 31)),
                                                            (date(2026, 1, 1), date(2026, 1, 10))]
