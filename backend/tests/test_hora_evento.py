"""Lectura de la hora del hecho en la sábana policial."""
from datetime import datetime, time

from services.excel_policia_processor import legacy_fingerprint_time, parse_event_time


def test_hora_hecho_exacta_gana_sobre_hora24():
    assert parse_event_time("21:35:00", 21) == time(21, 35)
    assert parse_event_time("7:05", "7") == time(7, 5)


def test_hora24_sola_da_la_hora_entera():
    assert parse_event_time(None, 21) == time(21, 0)
    assert parse_event_time("", "9") == time(9, 0)
    assert parse_event_time(None, 21.0) == time(21, 0)


def test_valores_de_excel():
    assert parse_event_time(time(14, 30), None) == time(14, 30)
    assert parse_event_time(datetime(1900, 1, 1, 8, 45), None) == time(8, 45)


def test_valores_invalidos_no_inventan_hora():
    assert parse_event_time("25:00", None) is None
    assert parse_event_time("SIN DATO", "NO REPORTA") is None
    assert parse_event_time(None, 24) is None


def test_huella_conserva_la_lectura_anterior():
    # Con HORA24 presente, la lectura anterior daba 00:00: la huella debe seguir igual
    # para que recargar una sábana no duplique los hechos ya cargados.
    assert legacy_fingerprint_time("21:35:00", 21) == time(0, 0)
    assert legacy_fingerprint_time("16:30:00", "16") == time(0, 0)
    assert legacy_fingerprint_time("17:48:00", None) == time(17, 48)
