import pandas as pd
import io
import hashlib
import uuid
import logging
import unicodedata
import re
import numpy as np
import json
import traceback
from datetime import datetime, date, time
from sqlalchemy.orm import Session
from sqlalchemy import text as sqlalchemy_text
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, IngestionIssue, StagingPoliciaSemanal, SabanaSnapshotRow, CatalogoConductaFuente
from db.models import EventType, Event
from services.geocoding_service import GeocodingService
from services.hechos_metrics import canonical_hecho_key
from services.sabana_history import build_coverage, claim_snapshot_record, normalize_source_id, snapshot_hecho_key, stable_record_key

logger = logging.getLogger("sisc_policia_processor")

COLUMN_ALIASES = {
    "id_fuente": ["HECHOS_ID", "ID_HECHO", "ID", "HECHO_ID", "COD_HECHO"],
    "conducta_original": ["DESCRIPCION_CONDUCTA", "CONDUCTA", "DELITO", "DESCRIPCIÓN_CONDUCTA", "CONDUCTA_SITIO"],
    "fecha_evento": ["FECHA_HECHO", "FECHA", "FECHA DEL HECHO", "FECHA_INCIDENTE"],
    "hora_evento": ["HORA_HECHO", "HORA", "HORA_INCIDENTE"],
    "hora_24": ["HORA24", "HORA_24", "FRANJA_HORA", "FRANJA_HORARIA"],
    "semana_num": ["NoSEMANA", "SEMANA", "NUM_SEMANA", "SEMANA_DEL"],
    "semana_texto": ["SEMANA_HECHO", "SEMANA_TEXTO"],
    "dia_semana": ["DIA_SEMANA", "DIA"],
    "barrio_original": ["BARRIOS_HECHO", "BARRIO", "BARRIO_HECHO", "DESCRIPCION_BARRIO"],
    "vereda_original": ["VEREDA", "VEREDA_HECHO", "NOMBRE_VEREDA"],
    "zona": ["ZONA", "ZONA_HECHO"],
    "arma_medio": ["ARMAS_MEDIOS", "ARMA", "MEDIO", "ARMAS O MEDIOS", "ARMA_MEDIO"],
    "modalidad": ["MODALIDAD", "MODALIDAD_HECHO"],
    "movil_agresor": ["MOVIL_AGRESOR", "MÓVIL_AGRESOR", "MOVIL_AGR"],
    "movil_victima": ["MOVIL_VICTIMA", "MÓVIL_VICTIMA", "MOVIL_VIC"],
    "clase_sitio": ["CLASE_SITIO", "SITIO", "LUGAR", "CLASE_DE_SITIO"],
    "sexo": ["GENERO", "SEXO", "SEXO_PERSONA"],
    "edad": ["EDAD", "EDAD_PERSONA"],
    "grupo_edad": ["AGRUPA_EDAD_PERSONA", "RANGO_EDAD", "GRUPO_ETAREO"],
    "fecha_reporte_fuente": ["FECHA_CREACION", "FECHA_CREACIÓN", "CREADO", "FECHA_REPORTE"],
    "municipio_fuente": ["MUNICIPIO_HECHO", "MUNICIPIO", "MPIO", "CIUDAD"]
}

class PoliciaJamundiProcessor:
    def __init__(self, db: Session, user_id: str = "SYSTEM"):
        self.db = db
        self.user_id = user_id
        self.catalogo_conductas = self._load_catalogo()

    def _load_catalogo(self):
        try:
            catalogo = self.db.query(CatalogoConductaFuente).filter(CatalogoConductaFuente.activo == True).all()
            return {c.valor_fuente.upper(): c for c in catalogo}
        except:
            return {}

    def _normalize_text(self, text):
        if not text or pd.isna(text): return ""
        text = str(text).strip().upper()
        # Remove accents
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        return text

    def _map_columns(self, df_cols):
        mapping = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                norm_alias = self._normalize_text(alias).replace(" ", "_")
                for col in df_cols:
                    if self._normalize_text(col).replace(" ", "_") == norm_alias:
                        mapping[canonical] = col
                        break
                if canonical in mapping: break
        return mapping

    def _generate_fingerprint(self, data):
        # Fingerprint expandido para permitir múltiples víctimas en el mismo hecho
        raw = f"{data.get('id_fuente', '')}|{data['conducta_estandar']}|{data['fecha_evento']}|{data['hora_evento']}|{data['barrio_normalizado'] or data['vereda_normalizada']}|{data['sexo']}|{data['edad']}|{data['arma_medio']}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _truthy_value(self, value):
        if value is None:
            return False
        if isinstance(value, float) and pd.isna(value):
            return False
        text = str(value).strip()
        return text and text.upper() not in {"NAN", "NONE", "NULL", "NO REPORTA", "SIN INFORMACION", "SIN INFORMACI??N"}

    def _find_master_hecho(self, processed_data, fingerprint):
        # La base policial puede traer varias victimas/registros con el mismo HECHOS_ID.
        # Por eso la identidad maestra debe ser a nivel registro/victima, no solo por id_fuente.
        return self.db.query(HechoSeguridad).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fingerprint == fingerprint,
        ).first()

    def _run_cutoff(self, ingestion_id):
        if not ingestion_id:
            return None
        return self.db.query(SabanaSnapshotRow.fecha_evento).filter(
            SabanaSnapshotRow.ingestion_id == ingestion_id
        ).order_by(SabanaSnapshotRow.fecha_evento.desc()).scalar()

    def _should_update_master(self, existing_hecho, current_cutoff):
        if not existing_hecho:
            return True
        previous_cutoff = self._run_cutoff(existing_hecho.ingestion_id)
        if not previous_cutoff or not current_cutoff:
            return True
        return current_cutoff >= previous_cutoff

    def _apply_master_values(self, hecho, processed_data, data, conducta_raw, conducta_est, cat_delito, fingerprint, run_id):
        hecho.fuente_codigo = "POLICIA_SEMANAL"
        hecho.id_fuente = processed_data["id_fuente"] if processed_data["id_fuente"] else None
        hecho.ingestion_id = run_id
        hecho.conducta_original = str(conducta_raw)
        hecho.conducta_estandar = conducta_est
        hecho.categoria_delito = cat_delito
        hecho.fecha_evento = processed_data["fecha_evento"]
        hecho.hora_evento = processed_data["hora_evento"]
        hecho.semana_num = processed_data.get("semana_num")
        hecho.dia_semana = data.get("dia_semana")
        hecho.sexo = processed_data["sexo"]
        hecho.edad = processed_data["edad"]
        hecho.grupo_edad = data.get("grupo_edad") if self._truthy_value(data.get("grupo_edad")) else hecho.grupo_edad
        hecho.zona = data.get("zona") if self._truthy_value(data.get("zona")) else hecho.zona
        hecho.arma_medio = processed_data["arma_medio"]
        hecho.modalidad = data.get("modalidad") if self._truthy_value(data.get("modalidad")) else hecho.modalidad
        hecho.movil_agresor = data.get("movil_agresor") if self._truthy_value(data.get("movil_agresor")) else hecho.movil_agresor
        hecho.movil_victima = data.get("movil_victima") if self._truthy_value(data.get("movil_victima")) else hecho.movil_victima
        hecho.clase_sitio = data.get("clase_sitio") if self._truthy_value(data.get("clase_sitio")) else hecho.clase_sitio
        hecho.barrio_original = data.get("barrio_original") if self._truthy_value(data.get("barrio_original")) else hecho.barrio_original
        hecho.barrio_normalizado = processed_data["barrio_normalizado"] or hecho.barrio_normalizado
        hecho.vereda_original = data.get("vereda_original") if self._truthy_value(data.get("vereda_original")) else hecho.vereda_original
        hecho.vereda_normalizada = processed_data["vereda_normalizada"] or hecho.vereda_normalizada
        hecho.municipio = "JAMUNDI"
        hecho.estado_calidad = "APROBADO"
        hecho.fingerprint = fingerprint
        hecho.fecha_reporte_fuente = pd.to_datetime(data["fecha_reporte_fuente"]) if data.get("fecha_reporte_fuente") else hecho.fecha_reporte_fuente
        hecho.fecha_ingesta = datetime.utcnow()
        hecho.usuario_ingesta = self.user_id
        return hecho

    def _homologar_conducta(self, conducta_raw):
        val = self._normalize_text(conducta_raw)
        
        # 1. Intento por catálogo
        if val in self.catalogo_conductas:
            c = self.catalogo_conductas[val]
            return c.valor_estandar, c.categoria_delito
        
        # 2. Heurística robusta
        if any(x in val for x in ["HOMICIDIO", "MUERTE"]): return "Homicidio", "HOMICIDIO"
        if any(x in val for x in ["LESIONES", "HERIDO"]): return "Lesiones personales", "LESIONES"
        if any(x in val for x in ["HURTO", "ROBO"]):
            if "PERSONA" in val: return "Hurto a personas", "HURTO"
            if "RESIDENCIA" in val: return "Hurto a residencias", "HURTO"
            if "COMERCIO" in val: return "Hurto a comercio", "HURTO"
            if "MOTO" in val: return "Hurto a motocicletas", "HURTO"
            if "AUTO" in val: return "Hurto a automotores", "HURTO"
            return "Hurto (Otros)", "HURTO"
        if "VIOLENCIA" in val and "INTRAFAMILIAR" in val: return "Violencia intrafamiliar", "VIF"
        
        return "Delito General", "OTROS"

    def process(self, contents: bytes, filename: str):
        file_hash = hashlib.sha256(contents).hexdigest()
        
        # 1. Verificar si ya se proceso
        existing_run = self.db.query(IngestionRun).filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.hash_archivo == file_hash,
        ).first()
        backfill_existing = False
        if existing_run:
            has_snapshot = self.db.query(SabanaSnapshotRow.id).filter(
                SabanaSnapshotRow.ingestion_id == existing_run.id
            ).first() is not None
            if has_snapshot:
                logger.info(f"Archivo ya procesado: {filename}")
                return {"status": "skipped", "message": "Este archivo ya fue procesado anteriormente.", "ingestion_id": str(existing_run.id)}
            backfill_existing = True
            run = existing_run
            run.status = "IN_PROGRESS"
            run.usuario_carga = self.user_id
            logger.info(f"Completando foto historica para archivo existente: {filename}")
        else:
            # 2. Iniciar Run
            run = IngestionRun(
                fuente_codigo="POLICIA_SEMANAL",
                hash_archivo=file_hash,
                filename=filename,
                usuario_carga=self.user_id,
                status="IN_PROGRESS"
            )
            self.db.add(run)
        self.db.commit()

        try:
            df = pd.read_excel(io.BytesIO(contents))
            run = self.db.query(IngestionRun).filter(IngestionRun.id == run.id).first()
            run.total_filas = len(df)
            self.db.flush()
            
            mapping = self._map_columns(df.columns)
            
            # REFINAMIENTO DE MAPEO: Corregir si se seleccionó Clase de Sitio como Conducta
            if mapping.get("conducta_original") == "CLASE_SITIO" or "SITIO" in str(mapping.get("conducta_original")).upper():
                for col in df.columns:
                    if any(x in col.upper() for x in ["DELITO", "CONDUCTA"]):
                        mapping["conducta_original"] = col
                        break

            stats = {
                "aprobadas": 0, "con_observacion": 0, "rechazadas": 0,
                "duplicadas": 0, "fuera_territorio": 0, "georreferenciadas": 0,
                "nuevas_consolidadas": 0, "actualizadas_consolidadas": 0, "existentes_historico": 0,
                "repetidas_en_archivo": 0, "filas_snapshot": 0,
            }
            snapshot_keys = set()
            snapshot_coverage = []
            current_delivery_cutoff = None
            if mapping.get("fecha_evento"):
                valid_dates = pd.to_datetime(df[mapping["fecha_evento"]], errors="coerce").dropna()
                if not valid_dates.empty:
                    current_delivery_cutoff = valid_dates.max().date()

            for idx, row in df.iterrows():
                if idx > 0 and idx % 50 == 0:
                    self.db.commit()
                    run = self.db.query(IngestionRun).filter(IngestionRun.id == run.id).first()

                try:
                    with self.db.begin_nested():
                        # a. Guardar Staging
                        raw_dict = row.to_dict()
                        sanitized_payload = {}
                        for k, v in raw_dict.items():
                            k_str = str(k)
                            if pd.isna(v): sanitized_payload[k_str] = None
                            elif isinstance(v, (datetime, date, time, pd.Timestamp)): sanitized_payload[k_str] = v.isoformat()
                            elif isinstance(v, (np.integer, np.floating)): sanitized_payload[k_str] = v.item()
                            elif isinstance(v, np.ndarray): sanitized_payload[k_str] = v.tolist()
                            else: sanitized_payload[k_str] = str(v)

                        if not backfill_existing:
                            stg = StagingPoliciaSemanal(
                                ingestion_id=run.id,
                                fila_origen=idx + 2,
                                payload_json=sanitized_payload,
                                columnas_normalizadas={k: str(row[v]) if pd.notna(row[v]) else None for k, v in mapping.items()},
                                hash_archivo=file_hash
                            )
                            self.db.add(stg)

                        # b. Mapeo y Normalización
                        data = {canonical: (row[col] if pd.notna(row[col]) else None) for canonical, col in mapping.items()}
                        
                        # c. Filtro Territorial
                        muni = self._normalize_text(data.get("municipio_fuente", "JAMUNDI"))
                        if muni and "JAMUNDI" not in muni:
                            stats["fuera_territorio"] += 1
                            continue

                        # d. Validaciones DQ
                        issues = []
                        raw_fecha = data.get("fecha_evento")
                        converted_fecha = pd.to_datetime(raw_fecha, errors='coerce') if raw_fecha else None
                        
                        if not raw_fecha or pd.isna(converted_fecha):
                            issues.append(IngestionIssue(ingestion_id=run.id, fila=idx+2, regla="FECHA_INVALIDA", descripcion=f"La fecha '{raw_fecha}' no es válida", severidad="ERROR"))
                        
                        conducta_raw = data.get("conducta_original")
                        if not conducta_raw or pd.isna(conducta_raw):
                            issues.append(IngestionIssue(ingestion_id=run.id, fila=idx+2, regla="CONDUCTA_NULA", descripcion="La conducta es obligatoria", severidad="ERROR"))

                        if any(i.severidad == "ERROR" for i in issues):
                            for issue in issues: self.db.add(issue)
                            stats["rechazadas"] += 1
                            continue

                        # e. Homologación
                        conducta_est, cat_delito = self._homologar_conducta(conducta_raw)

                        # f. Georeferenciación básica
                        barrio_norm = self._normalize_text(data.get("barrio_original"))
                        barrio_norm = re.sub(r'\s+E\d+$', '', barrio_norm)
                        vereda_norm = self._normalize_text(data.get("vereda_original"))
                        
                        coords = GeocodingService.get_coords_for_localidad(barrio_norm or vereda_norm or "JAMUNDI")
                        lat, lng = coords if coords else (3.2612, -76.5365) 

                        # g. Preparar datos procesados para Deduplicación
                        raw_hora = data.get("hora_24") or data.get("hora_evento")
                        try:
                            if isinstance(raw_hora, time): occ_time = raw_hora
                            else:
                                converted_hora = pd.to_datetime(raw_hora, errors='coerce') if raw_hora else None
                                occ_time = converted_hora.time() if not pd.isna(converted_hora) else time(0,0)
                        except:
                            occ_time = time(0,0)

                        processed_data = {
                            "id_fuente": normalize_source_id(data.get("id_fuente")),
                            "conducta_estandar": conducta_est,
                            "fecha_evento": converted_fecha.date(),
                            "hora_evento": occ_time,
                            "barrio_normalizado": barrio_norm,
                            "vereda_normalizada": vereda_norm,
                            "sexo": self._normalize_text(data.get("sexo", "NO REPORTA")),
                            "edad": int(data["edad"]) if data.get("edad") and str(data["edad"]).isdigit() else 0,
                            "arma_medio": self._normalize_text(data.get("arma_medio", "NO REPORTA"))
                        }
                        
                        # h. Deduplicación por Fingerprint (Hecho + Víctima)
                        # Eliminamos la deduplicación estricta por id_fuente para aceptar múltiples víctimas
                        fp = self._generate_fingerprint(processed_data)
                        record_key = stable_record_key(sanitized_payload)
                        if not claim_snapshot_record(snapshot_keys, record_key):
                            stats["repetidas_en_archivo"] += 1
                            stats["duplicadas"] += 1
                            continue

                        semana_num = int(data["semana_num"]) if data.get("semana_num") and str(data["semana_num"]).isdigit() else None
                        processed_data["semana_num"] = semana_num
                        snapshot_row = SabanaSnapshotRow(
                            ingestion_id=run.id,
                            fila_origen=idx + 2,
                            record_key=record_key,
                            hecho_key=snapshot_hecho_key(processed_data["id_fuente"], fp),
                            id_fuente=processed_data["id_fuente"] or None,
                            anio=processed_data["fecha_evento"].year,
                            semana_num=semana_num,
                            fecha_evento=processed_data["fecha_evento"],
                            conducta_original=str(conducta_raw),
                            conducta_estandar=conducta_est,
                            categoria_delito=cat_delito,
                            barrio_normalizado=barrio_norm,
                            arma_medio=processed_data["arma_medio"],
                            dia_semana=str(data.get("dia_semana") or ""),
                            sexo=processed_data["sexo"],
                            edad=processed_data["edad"],
                            datos_normalizados={
                                "mes": processed_data["fecha_evento"].strftime("%b").lower(),
                                "vereda": vereda_norm,
                                "zona": str(data.get("zona") or ""),
                                "modalidad": str(data.get("modalidad") or ""),
                            },
                        )
                        self.db.add(snapshot_row)
                        stats["aprobadas"] += 1
                        stats["filas_snapshot"] += 1
                        snapshot_coverage.append((processed_data["fecha_evento"], semana_num))

                        exists_snapshot = self.db.query(SabanaSnapshotRow.id).filter(
                            SabanaSnapshotRow.ingestion_id != run.id,
                            SabanaSnapshotRow.record_key == record_key,
                        ).first()
                        master_hecho = self._find_master_hecho(processed_data, fp)

                        # i. Base maestra: una entrega reciente actualiza; una historica solo completa faltantes.
                        if master_hecho:
                            stats["duplicadas"] += 1
                            stats["existentes_historico"] += 1
                            hecho = master_hecho
                            if self._should_update_master(master_hecho, current_delivery_cutoff):
                                self._apply_master_values(hecho, processed_data, data, conducta_raw, conducta_est, cat_delito, fp, run.id)
                                stats["actualizadas_consolidadas"] += 1
                            else:
                                continue
                        else:
                            if exists_snapshot:
                                stats["duplicadas"] += 1
                                stats["existentes_historico"] += 1
                            hecho = HechoSeguridad()
                            self._apply_master_values(hecho, processed_data, data, conducta_raw, conducta_est, cat_delito, fp, run.id)
                            self.db.add(hecho)
                            stats["nuevas_consolidadas"] += 1

                        self.db.flush()

                        # j. Sync to Legacy Event
                        event_type = self.db.query(EventType).filter(EventType.category == cat_delito.upper()).first()
                        if not event_type:
                            event_type = EventType(category=cat_delito.upper(), is_delicto=True)
                            self.db.add(event_type)
                            self.db.flush()

                        hecho_key = canonical_hecho_key(
                            processed_data["id_fuente"], fp, hecho.id
                        )
                        legacy_external_id = (
                            "POLICIA_SEMANAL:"
                            + hashlib.sha256(hecho_key.encode()).hexdigest()
                        )
                        existing_event = self.db.query(Event).filter(
                            Event.source_name == "POLICIA_SEMANAL",
                            Event.external_id == legacy_external_id,
                        ).first()

                        if not existing_event:
                            existing_event = Event(
                                external_id=legacy_external_id,
                                source_name="POLICIA_SEMANAL",
                            )
                            self.db.add(existing_event)

                        existing_event.event_type_id = event_type.id
                        existing_event.occurrence_date = processed_data["fecha_evento"]
                        existing_event.occurrence_time = processed_data["hora_evento"]
                        existing_event.barrio = barrio_norm or vereda_norm or "JAMUNDI"
                        existing_event.descripcion = f"[{conducta_est}] {data.get('modalidad', '')} - {data.get('arma_medio', '')}"
                        existing_event.ingestion_id = run.id
                        self.db.flush()
                        self.db.execute(
                            sqlalchemy_text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                            {"lng": lng, "lat": lat, "id": existing_event.id},
                        )
                        if coords: stats["georreferenciadas"] += 1

                except Exception as e:
                    logger.error(f"Error procesando fila {idx}: {e}")
                    try:
                        self.db.add(IngestionIssue(ingestion_id=run.id, fila=idx+2, regla="ERROR_SISTEMA", descripcion=str(e)[:250], severidad="ERROR"))
                    except: pass
                    stats["rechazadas"] += 1

            # Finish run
            run = self.db.query(IngestionRun).filter(IngestionRun.id == run.id).first()
            run.aprobadas = stats["aprobadas"]
            run.rechazadas = stats["rechazadas"]
            run.duplicadas = stats["duplicadas"]
            run.fuera_territorio = stats["fuera_territorio"]
            run.georreferenciadas = stats["georreferenciadas"]
            run.status = "COMPLETED"
            run.fecha_fin = datetime.utcnow()
            run.resumen = {
                "top_conductas": df[mapping.get("conducta_original")].value_counts().head(5).to_dict() if "conducta_original" in mapping else {},
                "snapshot": {
                    "filas": stats["filas_snapshot"],
                    "nuevas_consolidadas": stats["nuevas_consolidadas"],
                    "actualizadas_consolidadas": stats["actualizadas_consolidadas"],
                    "existentes_historico": stats["existentes_historico"],
                    "repetidas_en_archivo": stats["repetidas_en_archivo"],
                    "coverage": build_coverage(snapshot_coverage),
                },
            }
            
            self.db.commit()
            return {"status": "success", "ingestion_id": str(run.id), "stats": stats}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Fallo crítico en procesador: {traceback.format_exc()}")
            run = self.db.query(IngestionRun).filter(IngestionRun.id == run.id).first()
            if run:
                run.status = "FAILED"
                run.fecha_fin = datetime.utcnow()
                run.resumen = {"error": str(e)}
                self.db.commit()
            raise e
