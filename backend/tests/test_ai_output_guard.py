from services.ai_output_guard import extract_numbers, verify_ai_text

DATOS = """
- Periodo: enero a junio de 2026.
- Hurto Personas: 516 casos; -25.6% frente al mismo periodo de 2025.
- Lesiones Personales: 401 casos; -8.0% frente al mismo periodo de 2025.
- Hurto Residencias: 92 casos; 12.2% frente al mismo periodo de 2025.
- Registros unicos: 1052
- Poblacion de Jamundi: 180,942 habitantes.
"""


def test_colombian_number_formats():
    assert [str(n) for n in extract_numbers("1.052 casos, 25,6% y 180.942 habitantes")] == ["1052", "25.6", "180942"]


def test_faithful_text_passes():
    texto = ("En 2026 el hurto a personas registra 516 casos y disminuyo 25,6% frente al mismo periodo de 2025; "
             "el hurto a residencias aumento 12,2%. Se registran 1.052 registros unicos.")
    assert verify_ai_text(texto, DATOS).ok


def test_invented_number_is_rejected():
    result = verify_ai_text("El hurto a personas bajo a 510 casos.", DATOS)
    assert not result.ok and "510" in result.problems[0]


def test_rounded_number_is_rejected():
    assert not verify_ai_text("Las lesiones cayeron cerca de 8,5%.", DATOS).ok


def test_wrong_direction_is_rejected():
    result = verify_ai_text("El hurto a personas aumento 25,6% frente a 2025.", DATOS)
    assert not result.ok and "Direccion contraria" in result.problems[0]
    assert not verify_ai_text("El hurto a residencias disminuyo 12,2%.", DATOS).ok


def test_text_without_numbers_passes_and_empty_fails():
    assert verify_ai_text("Lectura descriptiva sin cifras adicionales.", DATOS).ok
    assert not verify_ai_text("   ", DATOS).ok


def test_extra_allowed_numbers():
    texto = "Ante emergencias llame al 123. Poblacion: 180.942 habitantes."
    assert not verify_ai_text(texto, DATOS).ok
    assert verify_ai_text(texto, DATOS, extra_allowed=["123"]).ok


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_redactar_verificado_uses_ai_text_only_when_faithful(monkeypatch):
    import api.ia as ia

    monkeypatch.setattr(ia, "AI_PROVIDER", "MISTRAL")

    async def fiel(_):
        return "El hurto a personas disminuyo 25,6% (516 casos)."

    async def inventa(_):
        return "El hurto a personas bajo a 480 casos."

    async def falla(_):
        raise RuntimeError("timeout")

    monkeypatch.setattr(ia, "call_mistral", fiel)
    ok = _run(ia.redactar_verificado("prompt", DATOS, respaldo="respaldo"))
    assert ok["text"].startswith("El hurto") and ok["verified"] and not ok["fallback"]

    monkeypatch.setattr(ia, "call_mistral", inventa)
    bad = _run(ia.redactar_verificado("prompt", DATOS, respaldo="respaldo"))
    assert bad["text"] == "respaldo" and bad["fallback"] and "480" in bad["problems"][0]

    monkeypatch.setattr(ia, "call_mistral", falla)
    down = _run(ia.redactar_verificado("prompt", DATOS, respaldo="respaldo"))
    assert down["text"] == "respaldo" and down["fallback"]
