import io
import zipfile
from datetime import date
from xml.sax.saxutils import escape

import pytest

from services.act_reader import (
    evaluate_deadline,
    paragraphs_from_lines,
    read_act,
    split_responsible,
)
from services.council_commitments_service import similarity

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _p(text):
    return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def _table(rows):
    cells = "".join(
        "<w:tr>" + "".join(f"<w:tc>{_p(cell)}</w:tc>" for cell in row) + "</w:tr>" for row in rows
    )
    return f"<w:tbl>{cells}</w:tbl>"


def docx(*blocks):
    body = "".join(_table(block) if isinstance(block, list) else _p(block) for block in blocks)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document {NS}><w:body>{body}</w:body></w:document>')
    return buffer.getvalue()


HEADER = [["ACTA No.", "49"], ["FECHA (DD/MM/AAAA):", "25/06/2026"]]


def test_table_of_commitments_in_consejo():
    content = docx(
        HEADER,
        "Objetivo: Sesión ordinaria del Consejo de Seguridad del municipio",
        [["COMPROMISO", "RESPONSABLE", "FECHA"],
         ["Instalar cámaras en el parque principal", "Secretaría de Seguridad", "30/07/2026"],
         ["Presentar informe de hurtos", "Policía Nacional", "Próximo consejo"],
         ["Revisar alumbrado de la vía", "Todas las entidades", "30/07/2025"]],
    )
    reading, reread = read_act(content, "acta.docx")
    assert reading.instance == "CONSEJO_SEGURIDAD"
    assert reading.act_number == "49" and reading.act_date == "2026-06-25"
    assert [item.method for item in reading.proposals] == ["TABLA"] * 3
    first, second, third = reading.proposals
    assert first.deadline_date == "2026-07-30" and first.responsible == "Secretaría de Seguridad"
    assert "PLAZO_VAGO" in second.flags
    assert "FECHA_ANIO_DISTINTO" in third.flags and "RESPONSABLE_GENERICO" in third.flags
    codes = {warning["code"] for warning in reading.warnings}
    assert {"FECHA_ANIO_DISTINTO", "PLAZOS_INDEFINIDOS"} <= codes
    assert reread == []


def test_list_of_commitments_keeps_word_paragraphs_separate():
    content = docx(
        HEADER,
        "Objetivo: Reunión semanal de planeación de seguridad",
        "Compromisos",
        "Policía Nacional: Realizar patrullajes en el barrio Terranova",
        "Secretaría de Gobierno: Convocar mesa con comerciantes del centro",
        "Siendo las 5 p. m. se da por terminada la reunión",
    )
    reading, _ = read_act(content, "acta.docx")
    assert reading.instance == "PLANEACION_SEMANAL"
    texts = [item.text for item in reading.proposals]
    assert len(texts) == 2, texts
    assert reading.proposals[0].responsible == "Policía Nacional"
    assert texts[0].startswith("Realizar patrullajes")


def test_empty_commitments_table_is_warned():
    content = docx(
        HEADER,
        "Objetivo: Sesión del Comité Civil de Convivencia",
        [["COMPROMISO", "RESPONSABLE", "FECHA"], ["", "", ""]],
    )
    reading, _ = read_act(content, "acta.docx")
    assert reading.instance == "COMITE_CIVIL_CONVIVENCIA"
    codes = {warning["code"] for warning in reading.warnings}
    assert {"SIN_COMPROMISOS", "TABLA_VACIA"} <= codes


def test_approval_with_votes_and_copied_closing_date():
    content = docx(
        [["ACTA No.", "6"], ["FECHA (DD/MM/AAAA):", "16/07/2026"]],
        "Objetivo: Comité Territorial de Orden Público",
        "La Secretaría propone distribuir los recursos del fondo entre Policía y Ejército.",
        "Aprobación",
        "Los miembros del comité votan (5): de acuerdo con lo propuesto:",
        [["Policía Nacional", "SI"], ["Ejército Nacional", "SI"], ["Personería", "SI"]],
        "Para constancia se firma hoy 12 de marzo de 2026.",
    )
    reading, _ = read_act(content, "acta.docx")
    assert reading.instance == "COMITE_ORDEN_PUBLICO"
    agreement = next(item for item in reading.proposals if item.kind == "ACUERDO")
    assert agreement.text.startswith("Aprobado: La Secretaría propone distribuir")
    assert "VOTOS_3" in agreement.flags
    assert any(warning["code"] == "CIERRE_FECHA_DISTINTA" for warning in reading.warnings)


def test_reread_commitments_are_not_new():
    content = docx(
        HEADER,
        "Objetivo: Consejo de Seguridad",
        "Lectura de compromisos",
        "Lectura de compromisos",
        "La Policía presentará el informe de cámaras pendiente desde abril.",
        "Contexto del municipio",
    )
    reading, reread = read_act(content, "acta.docx")
    assert reread == ["La Policía presentará el informe de cámaras pendiente desde abril"]
    assert reading.proposals == []


def test_pdf_lines_are_joined_but_headings_are_not():
    lines = ["Compromisos", "Policía Nacional: Realizar patrullajes en el", "sector de Potrerito.", "Aprobación"]
    assert paragraphs_from_lines(lines) == [
        "Compromisos", "Policía Nacional: Realizar patrullajes en el sector de Potrerito.", "Aprobación",
    ]


def test_deadline_and_responsible_helpers():
    assert evaluate_deadline("15/08/2026", date(2026, 6, 25)) == (date(2026, 8, 15), [])
    assert evaluate_deadline("10/06/2026", date(2026, 6, 25))[1] == ["FECHA_ANTERIOR_AL_ACTA"]
    assert evaluate_deadline(None, date(2026, 6, 25))[1] == ["SIN_PLAZO"]
    responsible, text = split_responsible("Por parte de la Secretaría de Salud, realizar jornada de vacunación")
    assert responsible == "Secretaría de salud" and text == "Realizar jornada de vacunación"


def test_similarity_finds_repeated_commitment():
    assert similarity("Presentar informe de cámaras de videovigilancia", "Informe sobre cámaras de videovigilancia pendientes") >= 0.5
    assert similarity("Presentar informe de cámaras", "Jornada de vacunación canina") == 0.0


def _raw_docx(xml):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def test_word_with_entity_declarations_is_rejected():
    xml = ('<?xml version="1.0"?><!DOCTYPE w [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
           f'<w:document {NS}><w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>')
    with pytest.raises(ValueError, match="no es válido"):
        read_act(_raw_docx(xml), "acta.docx")


def test_zip_bomb_is_rejected_before_decompressing(monkeypatch):
    import services.act_reader as reader

    monkeypatch.setattr(reader, "MAX_DOCX_XML_BYTES", 1000)
    padding = "<w:p><w:r><w:t>" + "x" * 5000 + "</w:t></w:r></w:p>"
    content = _raw_docx(f"<w:document {NS}><w:body>{padding}</w:body></w:document>")
    assert len(content) < 1000  # comprimido es pequeño; descomprimido supera el límite
    with pytest.raises(ValueError, match="demasiado grande"):
        read_act(content, "acta.docx")


def test_pdf_bullets_entity_without_de_and_closing_line():
    lines = [
        "Acta No. 27 Hora inicial: 11:30 a.m.",
        "Fecha (dd/mm/aaaa): 26/03/2026 Objetivo: Comité Territorial de Orden Público en el Municipio de Jamundí.",
        "Compromisos",
        " Secretaría Seguridad y Convivencia buscará saber cuánto es el recurso disponible.",
        " Se finaliza con el llamado a lista y confirmación de acuerdos por cada participante.",
    ]
    proposals = paragraphs_from_lines(lines)
    from services.act_reader import from_list, split_responsible as split

    items = from_list(proposals, date(2026, 3, 26))
    assert [item.text for item in items] == ["Buscará saber cuánto es el recurso disponible"]
    assert items[0].responsible == "Secretaría Seguridad y Convivencia"
    assert split(" Secretaría Seguridad y Convivencia presentará el proyecto")[0] == "Secretaría Seguridad y Convivencia"


def test_agreement_without_content_is_flagged_and_lead_in_is_trimmed():
    base = [[["ACTA No.", "27"], ["FECHA (DD/MM/AAAA):", "26/03/2026"]], "Objetivo: Comité Territorial de Orden Público", "Aprobación"]
    vague = read_act(docx(*base, "Carolina (Secretaría): Todos los miembros del comité presentes están de acuerdo con el propuesto"), "a.docx")[0]
    assert "ACUERDO_SIN_CONTENIDO" in vague.proposals[0].flags
    clear = read_act(docx(*base, "Carolina (Secretaría): Todos los miembros del comité presentes están de acuerdo que se incluyan al FONSET las recomendaciones del Ministerio"), "a.docx")[0]
    assert clear.proposals[0].text == "Aprobado: se incluyan al FONSET las recomendaciones del Ministerio"
    assert "ACUERDO_SIN_CONTENIDO" not in clear.proposals[0].flags


def test_responsible_before_colon_with_person_titles():
    assert split_responsible("La Secretaría de Gobierno Coordinar Visita: Programar e informar")[0] == "Secretaría de Gobierno"
    assert split_responsible("La Policía Nacional] Verificar Explosivos: Coordinar la revisión")[0] == "Policía Nacional"
    assert split_responsible("Comandante de Bomberos : Informar al Ejército")[0] == "Comandante de Bomberos"
    assert split_responsible("Actualizar plan de contingencia: Actualizar el plan")[0] is None


def test_agenda_after_commitments_heading_is_not_read_as_commitments():
    content = docx(
        HEADER, "Objetivo: Consejo de Seguridad extraordinario", "Compromisos",
        "1. Instalación de la sesión", "La alcaldesa convocó la reunión por los hechos recientes en la zona rural.",
    )
    assert read_act(content, "acta.docx")[0].proposals == []


def test_scanned_pdf_uses_ocr_only_when_authorized(monkeypatch):
    from services import institutional_agent_service as agents

    pages = [
        "Acta No. 107 Fecha (dd/mm/aaaa): 09/10/2025\n"
        "Objetivo: Concejo de Seguridad extraordinario por los explosivos en Robles\n"
        "Compromisos\n"
        "| COMPROMISO | RESPONSABLE | FECHA |\n| --- | --- | --- |\n"
        "| Entregar ayuda humanitaria a las familias afectadas | Secretaría de Gobierno | 10/10/2025 |\n"
    ]
    calls = []
    monkeypatch.setattr(agents.InstitutionalAgentService, "_extract_pdf_ocr",
                        lambda self, content, filename: calls.append(filename) or pages)
    scanned = b"%PDF-1.4 imagen sin capa de texto"
    monkeypatch.setattr("services.act_reader.pdf_blocks", lambda content: [])

    without = read_act(scanned, "acta.pdf")[0]
    assert calls == [] and without.proposals == [] and any(w["code"] == "SIN_TEXTO" for w in without.warnings)

    reading = read_act(scanned, "acta.pdf", use_ocr=True)[0]
    assert calls == ["acta.pdf"]
    assert reading.instance == "CONSEJO_SEGURIDAD" and reading.act_date == "2025-10-09"
    assert [(p.text, p.responsible, p.method) for p in reading.proposals] == [
        ("Entregar ayuda humanitaria a las familias afectadas", "Secretaría de Gobierno", "TABLA")]
    assert any(w["code"] == "LEIDA_CON_OCR" for w in reading.warnings)


def test_template_update_date_is_not_the_session_date():
    from services.act_reader import _fallback_date

    header = "CODIGO: DIE-GMI-F-03 FECHA ACTUALIZACION: 15/09/2023 VERSION: 1 ACTA NO. 91 REUNION DEL 25 DE AGOSTO DE 2025"
    assert _fallback_date(header) == date(2025, 8, 25)
