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
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, IngestionIssue, StagingPoliciaSemanal, CatalogoConductaFuente
from db.models import EventType, Event
from services.geocoding_service import GeocodingService
from services.hechos_metrics import canonical_hecho_key

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
        existing_run = self.db.query(IngestionRun).filter(IngestionRun.hash_archivo == file_hash).first()
        if existing_run:
            logger.info(f"Archivo ya procesado: {filename}")
            return {"status": "skipped", "message": "Este archivo ya fue procesado anteriormente.", "ingestion_id": str(existing_run.id)}

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
                "duplicadas": 0, "fuera_territorio": 0, "georreferenciadas": 0
            }

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
                            "id_fuente": str(data.get("id_fuente", "")),
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
                        exists_fp = self.db.query(HechoSeguridad).filter(
                            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", 
                            HechoSeguridad.fingerprint == fp
                        ).first()
                        
                        if exists_fp:
                            stats["duplicadas"] += 1
                            continue

                        # i. Fact Insertion
                        hecho = HechoSeguridad(
                            fuente_codigo="POLICIA_SEMANAL",
                            id_fuente=processed_data["id_fuente"] if processed_data["id_fuente"] else None,
                            ingestion_id=run.id,
                            conducta_original=str(conducta_raw),
                            conducta_estandar=conducta_est,
                            categoria_delito=cat_delito,
                            fecha_evento=processed_data["fecha_evento"],
                            hora_evento=processed_data["hora_evento"],
                            semana_num=int(data["semana_num"]) if data.get("semana_num") and str(data["semana_num"]).isdigit() else None,
                            dia_semana=data.get("dia_semana"),
                            sexo=processed_data["sexo"],
                            edad=processed_data["edad"],
                            grupo_edad=data.get("grupo_edad"),
                            zona=data.get("zona"),
                            arma_medio=processed_data["arma_medio"],
                            modalidad=data.get("modalidad"),
                            movil_agresor=data.get("movil_agresor"),
                            movil_victima=data.get("movil_victima"),
                            clase_sitio=data.get("clase_sitio"),
                            barrio_original=data.get("barrio_original"),
                            barrio_normalizado=barrio_norm,
                            vereda_original=data.get("vereda_original"),
                            vereda_normalizada=vereda_norm,
                            municipio="JAMUNDI",
                            estado_calidad="APROBADO",
                            fingerprint=fp,
                            fecha_reporte_fuente=pd.to_datetime(data["fecha_reporte_fuente"]) if data.get("fecha_reporte_fuente") else None,
                            usuario_ingesta=self.user_id
                        )
                        self.db.add(hecho)

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
                            new_event = Event(
                                external_id=legacy_external_id,
                                event_type_id=event_type.id,
                                occurrence_date=processed_data["fecha_evento"],
                                occurrence_time=processed_data["hora_evento"],
                                barrio=barrio_norm or vereda_norm or "JAMUNDI",
                                descripcion=f"[{conducta_est}] {data.get('modalidad', '')} - {data.get('arma_medio', '')}",
                                source_name="POLICIA_SEMANAL",
                                ingestion_id=run.id,
                            )
                            self.db.add(new_event)
                            self.db.flush()
                            self.db.execute(
                                sqlalchemy_text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                                {"lng": lng, "lat": lat, "id": new_event.id},
                            )
                        stats["aprobadas"] += 1
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
                "top_conductas": df[mapping.get("conducta_original")].value_counts().head(5).to_dict() if "conducta_original" in mapping else {}
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
