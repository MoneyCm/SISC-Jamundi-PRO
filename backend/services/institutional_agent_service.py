import calendar
import csv
import hashlib
import io
import os
import re
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Dict, Iterable, List, Optional
from xml.etree import ElementTree

import httpx
import pandas as pd
from sqlalchemy.orm import Session

from db.models_institutional import InstitutionalAgentFinding, InstitutionalAgentRun, InstitutionalDataBatch, InstitutionalIndicator


@dataclass
class Candidate:
    indicator: str
    value: Decimal
    unit: str = "casos"
    category: Optional[str] = None
    confidence: float = 1.0
    evidence: Optional[str] = None


class InstitutionalAgentService:
    EXTRACTOR_VERSION = "1.6"
    MISTRAL_OCR_MODEL = os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-4-0")
    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".pptx", ".docx", ".pdf"}

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def canonical_entity(value: str) -> str:
        normalized = InstitutionalAgentService._normalize(value)
        aliases = {
            "COMISARIA PRIMERA": "Comisar\u00eda Primera de Familia",
            "COMISARIA 1": "Comisar\u00eda Primera de Familia",
            "COMISARIA SEGUNDA": "Comisar\u00eda Segunda de Familia",
            "COMISARIA 2": "Comisar\u00eda Segunda de Familia",
            "INSPECCION SEGUNDA": "Inspecci\u00f3n Segunda",
            "INSPECCION 2": "Inspecci\u00f3n Segunda",
            "INSPECCION TERCERA": "Inspecci\u00f3n Tercera",
            "INSPECCION 3": "Inspecci\u00f3n Tercera",
        }
        for alias, canonical in aliases.items():
            if alias in normalized:
                return canonical
        return str(value or "").strip()
    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^A-Z0-9]+", " ", text.upper())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _decimal(value) -> Decimal:
        raw = str(value).strip().replace("$", "").replace(" ", "")
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif raw.count(".") > 1:
            raw = raw.replace(".", "")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"Valor no numerico: {value}") from exc

    def _extract_ooxml_text(self, content: bytes, extension: str) -> List[str]:
        prefix = "ppt/slides/slide" if extension == ".pptx" else "word/document.xml"
        blocks = []
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".xml")]
            for name in sorted(names):
                root = ElementTree.fromstring(archive.read(name))
                text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
                if text.strip():
                    blocks.append(text)
        return blocks

    def _extract_pdf_ocr(self, content: bytes, filename: str) -> List[str]:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY no esta configurada para OCR.")
        headers = {"Authorization": f"Bearer {api_key}"}
        file_id = None
        with httpx.Client(timeout=180.0) as client:
            try:
                upload = client.post(
                    "https://api.mistral.ai/v1/files",
                    headers=headers,
                    data={"purpose": "ocr", "visibility": "user"},
                    files={"file": (PurePath(filename).name, content, "application/pdf")},
                )
                upload.raise_for_status()
                file_id = upload.json()["id"]

                signed = None
                for attempt in range(5):
                    signed = client.get(
                        f"https://api.mistral.ai/v1/files/{file_id}/url",
                        headers=headers,
                        params={"expiry": 1},
                    )
                    if signed.is_success:
                        break
                    if signed.status_code == 404 and attempt < 4:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    signed.raise_for_status()
                if signed is None or not signed.is_success:
                    raise RuntimeError("Mistral recibio el archivo pero no habilito su lectura temporal.")
                document_url = signed.json()["url"]

                response = client.post(
                    "https://api.mistral.ai/v1/ocr",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": self.MISTRAL_OCR_MODEL,
                        "document": {"type": "document_url", "document_url": document_url},
                        "table_format": "markdown",
                        "confidence_scores_granularity": "page",
                    },
                )
                response.raise_for_status()
                pages = response.json().get("pages") or []
                return [page.get("markdown", "") for page in pages if page.get("markdown")]
            finally:
                if file_id:
                    try:
                        client.delete(f"https://api.mistral.ai/v1/files/{file_id}", headers=headers)
                    except Exception:
                        pass
    def _structured_rows(self, content: bytes, extension: str) -> List[Dict]:
        if extension == ".csv":
            return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace"))))
        workbook = pd.read_excel(io.BytesIO(content), sheet_name=None)
        rows = []
        for frame in workbook.values():
            rows.extend(frame.dropna(how="all").to_dict(orient="records"))
        return rows

    def _parse_structured(self, content: bytes, extension: str) -> List[Candidate]:
        aliases = {"INDICADOR": "indicator", "CATEGORIA": "category", "VALOR": "value", "UNIDAD": "unit"}
        candidates = []
        for raw_row in self._structured_rows(content, extension):
            row = {aliases.get(self._normalize(key), self._normalize(key)): value for key, value in raw_row.items()}
            indicator = row.get("indicator")
            if indicator is None or not str(indicator).strip():
                continue
            candidates.append(Candidate(
                indicator=str(indicator).strip(),
                category=str(row.get("category") or "").strip() or None,
                value=self._decimal(row.get("value")),
                unit=str(row.get("unit") or "casos").strip(),
                confidence=1.0,
                evidence="Fila estructurada de la plantilla institucional.",
            ))
        return candidates

    @staticmethod
    def _numbers(segment: str) -> List[Decimal]:
        values = []
        for raw in re.findall(r"(?<![\d/])\d[\d.,]*(?![\d/])", segment):
            try:
                number = Decimal(raw.replace(".", "").replace(",", "."))
            except InvalidOperation:
                continue
            if number not in {Decimal(year) for year in range(2017, 2031)}:
                values.append(number)
        return values

    def _candidate(self, block: str, indicator: str, start: str, end: Optional[str], pick: str, unit: str):
        normalized = self._normalize(block)
        start_index = normalized.find(start)
        if start_index < 0:
            return None
        segment = normalized[start_index + len(start):]
        if end:
            end_index = segment.find(end)
            if end_index >= 0:
                segment = segment[:end_index]
        segment = segment[:900]
        values = self._numbers(segment)
        if not values:
            return None
        value = values[0] if pick == "first" else values[-1]
        return Candidate(indicator, value, unit, confidence=0.75, evidence=segment[:300])

    def _parse_family_narrative(self, blocks: Iterable[str], period: Optional[str]) -> List[Candidate]:
        text = self._normalize(" ".join(blocks))
        if "COMISARIA" not in text:
            return []

        target_month = None
        target_year = None
        if period and re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", period):
            target_year = period[:4]
            target_month = int(period[-2:])
        month_labels = {
            1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
            5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
            9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
        }
        marker = None
        if target_month and target_year:
            marker = f"DE ENERO A 30 DE {month_labels[target_month]} {target_year}"
        if marker and marker in text:
            segment = text[text.index(marker) + len(marker):]
            later_markers = [
                f"DE ENERO A 30 DE {month_labels[month]} {target_year}"
                for month in range(target_month + 1, 13)
                if f"DE ENERO A 30 DE {month_labels[month]} {target_year}" in segment
            ]
            end_positions = [segment.index(value) for value in later_markers]
            if " DIFICULTADES " in segment:
                end_positions.append(segment.index(" DIFICULTADES "))
            if end_positions:
                segment = segment[:min(end_positions)]
        else:
            segment = text

        rules = [
            ("Denuncias por violencias de genero y contexto familiar", r"RECIBIO (\d+) DENUNCIAS POR VIOLENCIAS BASADAS EN GENERO Y OTRAS VIOLENCIAS EN EL CONTEXTO FAMILIAR", "casos"),
            ("Solicitudes de verificacion de derechos de NNA", r"RECIBIO UN TOTAL DE (\d+) SOLICITUDES PARA VERIFICACION DE GARANTIA DE DERECHOS", "solicitudes"),
            ("Casos reportados en zona urbana", r"ZONA URBANA DEL MUNICIPIO CON (\d+) CASOS", "casos"),
            ("Casos reportados en zona rural", r"FRENTE A (\d+) CASOS PRESENTADOS EN DIFERENTES CORREGIMIENTOS", "casos"),
            ("Casos de violencia intrafamiliar atendidos", r"DURANTE (?:ESTE PERIODO|EL PERIODO) SE ATENDIERON (\d+) CASOS DE VIOLENCIA INTRAFAMILIAR", "casos"),
            ("Verificaciones de derechos de NNA", r"(\d+) VERIFICACIONES DE DERECHOS DE NINOS NINAS Y ADOLESCENTES", "actuaciones"),
            ("Procesos Administrativos de Restablecimiento de Derechos", r"(?:PROCESOS ADMINISTRATIVOS DE RESTABLECIMIENTO DE DERECHOS SUMARON|SE DETERMINO APERTURAR Y O DAR CONTINUIDAD A) (\d+)", "procesos"),
            ("Medidas de proteccion urgentes", r"SE ADOPTARON (\d+) MEDIDAS DE PROTECCION URGENTES", "medidas"),
            ("Medidas de proteccion definitivas", r"MEDIDAS DE PROTECCION URGENTES Y (\d+) DEFINITIVAS", "medidas"),
            ("Sanciones por incumplimiento", r"SE IMPUSIERON (\d+) SANCIONES POR INCUMPLIMIENTO", "sanciones"),
            ("Casos de violencia contra adultos mayores", r"(?:SE IDENTIFICARON|SE PUDO DETERMINAR QUE) (\d+)(?: CASOS DE VIOLENCIA CONTRA ADULTOS MAYORES| DE ESTAS PRESUNTAS VICTIMAS SON ADULTOS MAYORES)", "casos"),
            ("PARD con institucionalizacion", r"DE LOS CUALES (\d+) DERIVARON EN INSTITUCIONALIZACION", "procesos"),
            ("PARD con permanencia en medio familiar", r"Y (\d+) EN MEDIO FAMILIAR", "procesos"),
            ("Atenciones de psicologia", r"EL AREA DE PSICOLOGIA REALIZO (\d+) ATENCIONES", "atenciones"),
            ("Atenciones de trabajo social", r"TRABAJO SOCIAL ADELANTO (\d+)", "atenciones"),
            ("Despachos comisorios recibidos", r"HASTA [A-Z]+ SE RECIBIERON (\d+) DESPACHOS COMISORIOS", "despachos"),
        ]
        candidates = []
        for indicator, pattern, unit in rules:
            match = re.search(pattern, segment)
            if not match:
                continue
            candidates.append(Candidate(
                indicator=indicator,
                value=Decimal(match.group(1)),
                unit=unit,
                category="Gestion de comisaria",
                confidence=0.85,
                evidence=match.group(0)[:300],
            ))
        return candidates

    def _parse_reports(self, blocks: Iterable[str], program: str, period: Optional[str] = None) -> List[Candidate]:
        rules = []
        if "COMIS" in self._normalize(program):
            rules = [
                ("Nuevos procesos de violencia en el contexto familiar", "APERTURA NUEVO PROCESO POR V I F", "EN GENERAL", "last", "casos"),
                ("Audiencias realizadas", "TOTAL AUDIENCIAS REALIZADAS", "DURANTE", "last", "casos"),
                ("Medidas de proteccion urgentes", "MEDIDA DE PROTECCION POLICIVA URGENTE", "MEDIDAS DEFINITIVAS", "last", "casos"),
                ("Medidas de proteccion definitivas", "MEDIDAS DEFINITIVAS", "TOTAL", "last", "casos"),
                ("Procesos Administrativos de Restablecimiento de Derechos", " PARD ", None, "last", "casos"),
                ("Acompanamientos psicologicos", "VALORACION PSICOLOGICA", None, "last", "casos"),
                ("Valoraciones de trabajo social", "VALORACION TRABAJO SOCIAL", None, "last", "casos"),
            ]
        elif "INSPE" in self._normalize(program):
            rules = [
                ("Certificados de residencia o vecindad", "CERTIFICADO RESIDENCIA Y O VECINDAD", "CERTIFICACIONES POR PERDIDA", "first", "tramites"),
                ("Constancias por perdida de documentos", "CERTIFICACIONES POR PERDIDA DE DOCUMENTOS", "RESOLUCION CERTIFICADO", "first", "tramites"),
                ("Resoluciones de certificado de defuncion", "RESOLUCION CERTIFICADO DE DEFUNCION", "TOTAL RECAUDO", "first", "tramites"),
                ("Recaudo por tramites", "TOTAL RECAUDO POR TRAMITES", None, "last", "COP"),
            ]
        found = {}
        for block in blocks:
            for indicator, start, end, pick, unit in rules:
                if indicator not in found:
                    candidate = self._candidate(block, indicator, start, end, pick, unit)
                    if candidate:
                        found[indicator] = candidate
        results = list(found.values())
        if "COMIS" in self._normalize(program):
            narrative = self._parse_family_narrative(blocks, period)
            narrative_names = {item.indicator for item in narrative}
            results = [item for item in results if item.indicator not in narrative_names] + narrative
        if "INSPE" in self._normalize(program):
            known = {item.indicator for item in results}
            results.extend(item for item in self._parse_inspection_consolidated(blocks) if item.indicator not in known)
        return results

    def detect_metadata(self, content: bytes, filename: str, blocks_override: Optional[List[str]] = None) -> Dict:
        extension = PurePath(filename).suffix.lower()
        blocks = []
        if extension in {".pptx", ".docx"}:
            try:
                blocks = self._extract_ooxml_text(content, extension)
            except Exception:
                blocks = []
        elif extension in {".csv", ".xlsx"}:
            try:
                rows = self._structured_rows(content, extension)[:50]
                blocks = [" ".join(f"{key} {value}" for key, value in row.items()) for row in rows]
            except Exception:
                blocks = []

        if blocks_override is not None:
            blocks = list(blocks_override)

        raw_text = f"{PurePath(filename).stem} " + " ".join(blocks)
        normalized = self._normalize(raw_text)
        evidence = []

        program = None
        if "COMISARIA" in normalized:
            program = "COMISARIAS"
            evidence.append("Se encontro la palabra COMISARIA.")
        elif "INSPECCION" in normalized:
            program = "INSPECCIONES"
            evidence.append("Se encontro la palabra INSPECCION.")

        reporting_entity = None
        entity_rules = [
            ("Comisaria Primera de Familia", ["COMISARIA PRIMERA", "COMISARIA 1", "COMISARIA UNO"]),
            ("Comisaria Segunda de Familia", ["COMISARIA SEGUNDA", "COMISARIA 2", "COMISARIA DOS"]),
            ("Inspeccion Segunda", ["INSPECCION SEGUNDA", "INSPECCION 2", "INSPECCION DOS"]),
            ("Inspeccion Tercera", ["INSPECCION TERCERA", "INSPECCION 3", "INSPECCION TRES"]),
        ]
        for entity, patterns in entity_rules:
            if any(pattern in normalized for pattern in patterns):
                reporting_entity = entity
                evidence.append(f"Dependencia identificada: {entity}.")
                break

        month_names = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
            "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
            "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
            "NOVIEMBRE": 11, "DICIEMBRE": 12,
        }
        months = sorted({number for name, number in month_names.items() if re.search(rf"\b{name}\b", normalized)})
        years = sorted({int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)})
        period = f"{years[-1]}-{months[-1]:02d}" if years and months else None
        if period:
            evidence.append(f"Periodo final identificado: {period}.")

        cutoff_candidates = []
        for day_raw, month_raw, year_raw in re.findall(r"\b([0-3]?\d)[/-]([01]?\d)[/-](20\d{2})\b", raw_text):
            try:
                cutoff_candidates.append(date(int(year_raw), int(month_raw), int(day_raw)))
            except ValueError:
                continue
        textual_date_pattern = r"\b([0-3]?\d)\s+DE\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|SETIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)(?:\s+DE)?\s+(20\d{2})\b"
        for day_raw, month_name, year_raw in re.findall(textual_date_pattern, normalized):
            try:
                cutoff_candidates.append(date(int(year_raw), month_names[month_name], int(day_raw)))
            except ValueError:
                continue

        cutoff = max(cutoff_candidates).isoformat() if cutoff_candidates else None
        if cutoff:
            evidence.append(f"Fecha de corte explicita: {cutoff}.")

        cumulative_markers = ["ACUMULADO", "A CORTE", "ENERO A ", "ENERO HASTA", "ENERO SEPTIEMBRE"]
        reporting_basis = "CUMULATIVE" if len(months) > 1 or any(marker in normalized for marker in cumulative_markers) else "MONTHLY"
        evidence.append("Modalidad propuesta: acumulada." if reporting_basis == "CUMULATIVE" else "Modalidad propuesta: mensual.")

        confidence = 0.0
        confidence += 0.35 if program else 0
        confidence += 0.30 if reporting_entity else 0
        confidence += 0.25 if period else 0
        confidence += 0.10 if cutoff else 0

        reporting_entity = self.canonical_entity(reporting_entity) if reporting_entity else None

        return {
            "program": program,
            "reporting_entity": reporting_entity,
            "period": period,
            "cutoff_date": cutoff,
            "reporting_basis": reporting_basis,
            "confidence": round(confidence, 2),
            "requires_confirmation": confidence < 0.85,
            "evidence": evidence,
        }
    def _parse_inspection_consolidated(self, blocks: Iterable[str]) -> List[Candidate]:
        found = {}
        for block in blocks:
            normalized = self._normalize(block)
            if "CUADRO CONSOLIDADO DE ACTUACIONES" not in normalized:
                continue

            rules = [
                ("Actuaciones en procesos verbales abreviados", "PROCESOS VERBALES", "INFRACCIONES", "last", "actuaciones"),
                ("Infracciones urbanisticas gestionadas", "INFRACCIONES URBANISTICAS", "DESPACHOS", "last", "actuaciones"),
                ("Despachos comisorios gestionados", "DESPACHOS COMISORIOS", "PROCESOS ADMINISTRATIVOS", "last", "actuaciones"),
                ("Procesos administrativos de tramite policivo", "PROCESOS ADMINISTRATIVOS", "GESTION DE MEDIDAS", "first", "tramites"),
                ("Gestiones de medidas correctivas", "GESTION DE MEDIDAS CORRECTIVAS", "TOTAL RECAUDO", "first", "actuaciones"),
            ]
            for indicator, start, end, pick, unit in rules:
                candidate = self._candidate(block, indicator, start, end, pick, unit)
                if candidate:
                    found[indicator] = candidate

            total_match = re.search(
                r"TOTAL RECAUDO CON CORTE.*?20\d{2}\s+(\d{2,4})\s+\$",
                normalized,
            )
            if total_match:
                found["Total de actuaciones"] = Candidate(
                    "Total de actuaciones", Decimal(total_match.group(1)), "actuaciones",
                    confidence=0.85, evidence=total_match.group(0)[:200],
                )

            money_rules = [
                ("Recaudo total reportado", r"TOTAL\s+RECAUDO\s+CON\s+CORTE[\s\S]{0,220}?\$\s*([\d\s.,]+,\d{2})"),
                ("Recaudo por tramites administrativos", r"PROCESOS\s+ADMINISTRATIVOS[\s\S]{0,700}?\$\s*([\d\s.,]+,\d{2})"),
                ("Recaudo por medidas correctivas", r"GESTION\s+DE\s+MEDIDAS\s+CORRECTIVAS[\s\S]{0,350}?\$\s*([\d\s.,]+,\d{2})"),
            ]
            upper_block = unicodedata.normalize("NFKD", block.upper())
            upper_block = "".join(char for char in upper_block if not unicodedata.combining(char))
            for indicator, pattern in money_rules:
                match = re.search(pattern, upper_block)
                if not match:
                    continue
                digits = re.sub(r"\D", "", match.group(1))
                if len(digits) < 3:
                    continue
                value = Decimal(digits) / Decimal("100")
                found[indicator] = Candidate(
                    indicator, value, "COP", confidence=0.85, evidence=match.group(0)[-220:],
                )

        return list(found.values())
    def _privacy_findings(self, blocks: Iterable[str]) -> List[dict]:
        raw_text = "\n".join(blocks)
        normalized = self._normalize(raw_text)
        patterns = [
            ("POTENTIAL_EMAIL", r"\b[\w.+-]+@[\w.-]+\.[A-Z]{2,}\b", "Posible correo electronico detectado.", raw_text),
            ("POTENTIAL_PHONE", r"(?<!\d)(?:57\s*)?3\d{9}(?!\d)", "Posible telefono personal detectado.", normalized),
            ("POTENTIAL_ID", r"\b(?:CEDULA|DOCUMENTO|IDENTIFICACION)\s*\d{6,12}\b", "Posible documento de identidad detectado.", normalized),
        ]
        findings = []
        for code, pattern, message, source_text in patterns:
            match = re.search(pattern, source_text, flags=re.IGNORECASE)
            if match:
                findings.append({"code": code, "message": message, "evidence": match.group(0)[:80]})
        return findings

    def ingest(self, content: bytes, filename: str, program: str, reporting_entity: str, period: str, cutoff_date: date, reporting_basis: str, version: int, user_id: str, use_cloud_ocr: bool = False):
        extension = PurePath(filename).suffix.lower()
        run = InstitutionalAgentRun(
            source_filename=PurePath(filename).name,
            source_sha256=hashlib.sha256(content).hexdigest(),
            extractor_version=self.EXTRACTOR_VERSION,
            status="RECEIVED",
        )
        self.db.add(run)
        self.db.flush()

        if extension not in self.SUPPORTED_EXTENSIONS:
            run.status = "NEEDS_MANUAL_EXTRACTION"
            run.summary = "Formato no procesable automaticamente. Requiere plantilla CSV o XLSX."
            run.findings.append(InstitutionalAgentFinding(
                agent_name="intake", severity="HIGH", code="UNSUPPORTED_FORMAT",
                message=run.summary, blocks_publication=True,
            ))
            run.finished_at = datetime.utcnow()
            self.db.commit()
            return run
        if extension == ".pdf" and not use_cloud_ocr:
            run.status = "NEEDS_OCR_CONSENT"
            run.summary = "El PDF requiere autorizacion explicita para procesarse con Mistral OCR 4."
            run.findings.append(InstitutionalAgentFinding(
                agent_name="intake", severity="HIGH", code="CLOUD_OCR_CONSENT_REQUIRED",
                message=run.summary, blocks_publication=True,
            ))
            run.finished_at = datetime.utcnow()
            self.db.commit()
            return run
        blocks = []
        if extension in {".csv", ".xlsx"}:
            candidates = self._parse_structured(content, extension)
        elif extension == ".pdf":
            try:
                blocks = self._extract_pdf_ocr(content, filename)
                metadata = self.detect_metadata(b"", filename, blocks)
                missing_metadata = [key for key in ("program", "reporting_entity", "period") if not metadata.get(key)]
                program = metadata.get("program") or program
                reporting_entity = self.canonical_entity(metadata.get("reporting_entity") or reporting_entity)
                period = metadata.get("period") or period
                reporting_basis = metadata.get("reporting_basis") or reporting_basis
                inferred_cutoff = False
                if metadata.get("cutoff_date"):
                    cutoff_date = date.fromisoformat(metadata["cutoff_date"])
                elif metadata.get("period"):
                    year, month = [int(value) for value in period.split("-")]
                    cutoff_date = date(year, month, calendar.monthrange(year, month)[1])
                    inferred_cutoff = True
                if missing_metadata or inferred_cutoff:
                    detail = "Faltan: " + ", ".join(missing_metadata) if missing_metadata else f"Confirmar fecha de corte inferida: {cutoff_date.isoformat()}."
                    run.findings.append(InstitutionalAgentFinding(
                        agent_name="metadata", severity="HIGH", code="METADATA_REVIEW_REQUIRED",
                        message=detail, blocks_publication=True,
                    ))
                else:
                    run.findings.append(InstitutionalAgentFinding(
                        agent_name="metadata", severity="LOW", code="METADATA_AUTO_DETECTED",
                        message=f"IA identifico {reporting_entity}, periodo {period}, corte {cutoff_date.isoformat()} y modalidad {reporting_basis}.",
                        blocks_publication=False,
                    ))
                latest = self.db.query(InstitutionalDataBatch).filter_by(
                    program=program, reporting_entity=reporting_entity, period=period
                ).order_by(InstitutionalDataBatch.version.desc()).first()
                if latest and version <= latest.version:
                    version = latest.version + 1
                candidates = self._parse_reports(blocks, program, period)
            except Exception as exc:
                run.status = "OCR_FAILED"
                print(f"Mistral OCR error: {type(exc).__name__}: {exc}")
                run.summary = "El servicio Mistral OCR 4 no completo el procesamiento. Puedes intentarlo nuevamente; no se almaceno ni publico informacion."
                run.findings.append(InstitutionalAgentFinding(
                    agent_name="ocr", severity="HIGH", code="OCR_PROCESSING_FAILED",
                    message=run.summary, blocks_publication=True,
                ))
                run.finished_at = datetime.utcnow()
                self.db.commit()
                return run
        else:
            blocks = self._extract_ooxml_text(content, extension)
            candidates = self._parse_reports(blocks, program, period)
        batch = InstitutionalDataBatch(
            program=program.strip(), reporting_entity=self.canonical_entity(reporting_entity), period=period,
            cutoff_date=cutoff_date, reporting_basis=reporting_basis, source_reference=f"sha256:{run.source_sha256}",
            source_filename=run.source_filename, version=version, validation_status="PENDING",
            submitted_by=user_id,
        )
        for candidate in candidates:
            batch.indicators.append(InstitutionalIndicator(
                indicator=candidate.indicator, category=candidate.category, value=candidate.value,
                unit=candidate.unit, is_public=candidate.value >= 10, privacy_threshold=10,
                notes=f"Confianza: {candidate.confidence:.0%}. Evidencia: {candidate.evidence or ''}",
            ))
            if candidate.confidence < 0.9:
                run.findings.append(InstitutionalAgentFinding(
                    agent_name="extraction", severity="MEDIUM", code="REVIEW_EXTRACTED_VALUE",
                    message=f"Validar manualmente: {candidate.indicator} = {candidate.value}",
                    evidence=candidate.evidence, blocks_publication=True,
                ))
        for finding in self._privacy_findings(blocks):
            run.findings.append(InstitutionalAgentFinding(
                agent_name="privacy", severity="HIGH", code=finding["code"],
                message=finding["message"], evidence=finding["evidence"], blocks_publication=True,
            ))
        if not candidates:
            run.findings.append(InstitutionalAgentFinding(
                agent_name="extraction", severity="HIGH", code="NO_INDICATORS_FOUND",
                message="No se identificaron indicadores confiables. Cargar la plantilla institucional.",
                blocks_publication=True,
            ))
        self.db.add(batch)
        self.db.flush()
        run.batch_id = batch.id
        run.status = "REVIEW_REQUIRED" if any(item.blocks_publication for item in run.findings) else "READY_FOR_APPROVAL"
        run.summary = f"{len(candidates)} indicadores candidatos; {len(run.findings)} hallazgos."
        run.finished_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run