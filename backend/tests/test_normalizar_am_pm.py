"""La hora en español del RNMC ("p. m.") se convierte a AM/PM antes de leer fechas."""
from datetime import datetime

from services.file_reader import normalizar_am_pm


def test_spanish_am_pm_variants():
    assert normalizar_am_pm("11/03/2026 04:15:31 p. m.") == "11/03/2026 04:15:31 PM"
    assert normalizar_am_pm("15/10/2026 09:00:33 a. m.") == "15/10/2026 09:00:33 AM"
    assert normalizar_am_pm("15/10/2026 09:00:33 a.m.") == "15/10/2026 09:00:33 AM"
    assert normalizar_am_pm("15/10/2026 09:00:33 PM") == "15/10/2026 09:00:33 PM"


def test_values_without_am_pm_are_unchanged():
    assert normalizar_am_pm("14/06/2026") == "14/06/2026"
    assert normalizar_am_pm("2026-06-14 16:00:00") == "2026-06-14 16:00:00"
    assert normalizar_am_pm("RESOLUCION DE PAGO") == "RESOLUCION DE PAGO"
    fecha = datetime(2026, 6, 14)
    assert normalizar_am_pm(fecha) is fecha
    assert normalizar_am_pm(None) is None
