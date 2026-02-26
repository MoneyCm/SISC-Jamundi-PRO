import pandas as pd
import unicodedata
import logging
from datetime import datetime, date
from typing import List, Dict, Generator
import io
import hashlib

logger = logging.getLogger("sisc_api")

class NationalStatsProcessor:
    def __init__(self):
        self.municipios_cache = {} # Para memoizar normalizaciones
        
    def normalize_text(self, text: str) -> str:
        """
        Elimina tildes, mayúsculas y caracteres especiales.
        Ej: "BOGOTÁ, D.C." -> "BOGOTA"
        """
        if not isinstance(text, str):
            return str(text) if text is not None else ""
            
        # Normalizar unicode (NFD) y eliminar diacríticos
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        text = text.upper().strip()
        
        # Limpieza específica para municipios colombianos y formatos de archivo
        text = text.replace(", D.C.", "").replace(" D.C.", "")
        text = text.replace(".", "").replace("_", " ")
        return text

    def _generate_fingerprint(self, source_id: str, row: pd.Series, fecha_iso: str, cod_muni: str = None) -> str:
        """
        Genera un fingerprint determinístico basado en la fuente (IDEMPOTENCIA).
        Regla: NO usar CANTIDAD ni FILENAME en el hash para permitir actualizaciones.
        """
        
        # A) AFECTACION_FUERZA_PUBLICA
        if source_id == "AFECTACION_FUERZA_PUBLICA":
            fuerza = str(row.get('NOMBRE_FUERZA', ''))
            accion = str(row.get('ACCION', ''))
            categoria = str(row.get('CATEGORIA', ''))
            muni = cod_muni or str(row.get('COD_MUNI', ''))
            raw = f"{fecha_iso}|{muni}|{fuerza}|{accion}|{categoria}"
            
        # B) ASPERSION
        elif source_id == "ASPERSION":
            muni = cod_muni or str(row.get('COD_MUNI', ''))
            unidades = str(row.get('UNIDADES_DE_MEDIDA', ''))
            raw = f"{fecha_iso}|{muni}|{unidades}"
            
        # C) SEM_POLICIA
        elif source_id == "SEM_POLICIA":
            # FECHA_HECHO + DESCRIPCION_CONDUCTA + BARRIO/VEREDA + (INTERVALOS_HORA o HORA24) + MODALIDAD + ARMAS_MEDIOS
            conducta = str(row.get('DESCRIPCION_CONDUCTA', row.get('CONDUCTA', '')))
            barrio = str(row.get('BARRIOS_HECHO', row.get('BARRIO', row.get('VEREDA', ''))))
            # Prioridad de hora: HORA24 > HORA_HECHO > INTERVALOS_HORA
            hora = str(row.get('HORA24', row.get('HORA_HECHO', row.get('INTERVALOS_HORA', ''))))
            modo = str(row.get('MODALIDAD', ''))
            armas = str(row.get('ARMAS_MEDIOS', row.get('ARMA_MEDIO', '')))
            muni = str(row.get('MUNICIPIO_HECHO', str(row.get('HECHOS.MUNICIPIO', 'JAMUNDI'))))
            raw = f"{fecha_iso}|{muni}|{conducta}|{barrio}|{hora}|{modo}|{armas}"
            
        else:
            # Fallback genérico para otras fuentes
            # TIPO_DELITO + FECHA + MUNICIPIO + BARRIO + GENERO + MODALIDAD
            delito = str(row.get('DESCRIPCION_CONDUCTA', row.get('DELITO', '')))
            muni = str(row.get('MUNICIPIO_HECHO', 'JAMUNDI'))
            barrio = str(row.get('BARRIOS_HECHO', ''))
            gen = str(row.get('GENERO', ''))
            mod = str(row.get('MODALIDAD', ''))
            raw = f"{fecha_iso}|{muni}|{delito}|{barrio}|{gen}|{mod}"
            
        return hashlib.sha256(raw.encode()).hexdigest()

    def _infer_crime_type_id(self, name: str) -> str:
        name = name.upper()
        if "ASPERSION" in name: return "ASPERSION"
        if "AFECTACION" in name or "FUERZA PUBLICA" in name: return "AFECTACION_FUERZA_PUBLICA"
        if "SEM" in name or "SEMANAL" in name: return "SEM_POLICIA"
        if "RNMC" in name or "MEDIDAS GESTIONADAS" in name: return "INSPECCION_MEDIDAS_RNMC"
        return "GENERIC_CRIME"

    def process_excel(self, file_content: bytes, filename: str, inferred_crime_type: str = None) -> Generator[Dict, None, None]:
        # ... logic anterior hasta el loop ...
        """
        Procesa el archivo Excel usando pandas, que es mucho más robusto
        para los archivos del MinDefensa que openpyxl raw.
        """
        try:
            # Leer excel en memoria con pandas
            # Leer excel crudo sin headers para buscar donde empiezan (limitando a 20 filas para rendimiento)
            df_raw = pd.read_excel(io.BytesIO(file_content), header=None, nrows=20)
            
            if df_raw.empty:
                logger.error(f"El archivo {filename} está vacío.")
                return

            header_idx = -1
            # Buscar en las primeras 20 filas un indicador de header
            indicators = ["MUNICIPIO", "MPIO", "LUGAR", "CONDUCTA", "FECHA_HECHO"]
            for idx, row in df_raw.head(20).iterrows():
                row_str = [str(x).upper().strip() for x in row.values if pd.notna(x)]
                if any(any(ind in v for ind in indicators) for v in row_str):
                    header_idx = idx
                    break

            if header_idx == -1:
                logger.error(f"No se encontró fila de encabezado válida en {filename}")
                return

            # Liberar memoria de df_raw
            del df_raw
            import gc
            gc.collect()

            # Releer saltando el preámbulo y SOLO cargando las columnas estrictamente necesarias (Optimización OOM)
            # Lista de posibles variaciones de nombres de columnas que sí nos importan
            # Sin normalizar para la parte de lectura (ya que los espacios pueden estar presentes en el excel)
            important_cols = [
                "MUNICIPIO", "MPIO", "LUGAR", "DEPARTAMENTO", "DTO", "AÑO", "ANIO", "SEMANA", "BARRIO", "CONDUCTA",
                "FECHA", "CANTIDAD", "TOTAL", "VICTIMAS", "NUMERO_CASOS",
                "SEXO", "GENERO", "ZONA", "EDAD", "MODALIDAD", "ARMA", "MEDIO",
                "NOMBRE_FUERZA", "ACCION", "CATEGORIA", "COD_MUNI", "CVE_MUNI",
                "COD_DEPTO", "UNIDADES"
            ]
            def is_important_col(col_name):
                # Validar la columna contra nuestra lista blanca para evitar cargar MBs de datos inútiles
                norm_name = str(col_name).upper().strip()
                return any(imp in norm_name for imp in important_cols)

            df = pd.read_excel(
                io.BytesIO(file_content), 
                header=header_idx, 
                usecols=is_important_col
            )

            # Normalizar nombres de columnas post-lectura
            df.columns = [str(c).upper().strip().replace(" ", "_") if not pd.isna(c) else "" for c in df.columns]
            header_vals = df.columns.tolist()
            
            # Identificar columnas (Flexibilizado para SEM/VIF)
            col_municipio = next((c for c in header_vals if any(x in c for x in ["MUNICIPIO", "HECHOS.MUNICIPIO", "MUNICIPIO_HECHO", "LUGAR", "MPIO"])), None)
            col_depto = next((c for c in header_vals if any(x in c for x in ["DEPARTAMENTO", "DEPTO", "DEPARTAMENTO_HECHO", "DTO"])), None)
            
            if not col_municipio:
                logger.error(f"Faltan columna de MUNICIPIO en {filename}: {header_vals}")
                return
            
            # Fecha
            col_fecha = next((c for c in header_vals if any(x in c for x in ["FECHA_HECHO", "FECHA_DANE", "FECHA"])), None)
            
            # Cantidad
            col_cantidad = next((c for c in header_vals if any(x in c for x in ["CANTIDAD", "TOTAL", "VICTIMAS", "NUMERO_CASOS"])), None)
            
            # Discriminadores Extra para evitar colisiones
            col_sexo = next((c for c in header_vals if any(x in c for x in ["SEXO", "GENERO"])), None)
            col_zona = next((c for c in header_vals if "ZONA" in c), None)
            col_edad = next((c for c in header_vals if "EDAD" in c), None)
            col_modalidad = next((c for c in header_vals if any(x in c for x in ["MODALIDAD", "ARMA", "MEDIO"])), None)
            
            # Columnas específicas Fuerza Pública
            col_fuerza = next((c for c in header_vals if "NOMBRE_FUERZA" in c), None)
            col_accion = next((c for c in header_vals if "ACCION" in c), None)
            col_categoria = next((c for c in header_vals if "CATEGORIA" in c), None)
            col_codigo_dane = next((c for c in header_vals if any(x in c for x in ["COD_MUNI", "CVE_MUNI"])), None)

            file_year = self._extract_year_from_filename(filename)
            tipo_delito = inferred_crime_type or self._infer_crime_type(filename)
            
            # --- DETECTAR SI ES ASPERSIÓN ---
            is_aspersion = tipo_delito == "ASPERSION" or all(x in header_vals for x in ["COD_DEPTO", "COD_MUNI", "UNIDADES_DE_MEDIDA"])
            
            # Columnas específicas Aspersión
            col_cod_depto = next((c for c in header_vals if "COD_DEPTO" in c), None)
            col_cod_muni = next((c for c in header_vals if "COD_MUNI" in c), None)
            col_unidades = next((c for c in header_vals if "UNIDADES_DE_MEDIDA" in c), None)

            # Iterar sobre las filas
            for _, row in df.iterrows():
                try:
                    municipio = row[col_municipio]
                    if pd.isna(municipio) or str(municipio).strip().upper() == "TOTAL" or str(municipio).strip() == "":
                        continue
                        
                    dept = row[col_depto] if col_depto else ""
                    municipio_norm = self.normalize_text(str(municipio))
                    
                    # Fecha
                    fecha_obj = None
                    if col_fecha and not pd.isna(row[col_fecha]):
                        fecha_raw = row[col_fecha]
                        fecha_obj = self._parse_date_openpyxl(fecha_raw)
                    
                    if not fecha_obj:
                        fecha_obj = date(file_year, 1, 1)

                    # Cantidad (como float para hectáreas)
                    cantidad_val = 1.0
                    if col_cantidad and not pd.isna(row[col_cantidad]):
                        try:
                            cantidad_val = float(row[col_cantidad])
                        except (ValueError, TypeError):
                            pass

                    # ASPERSIÓN: Guardar en contexto territorial (VALLE o JAMUNDI)
                    if is_aspersion:
                        cod_d = int(row[col_cod_depto]) if col_cod_depto and not pd.isna(row[col_cod_depto]) else 0
                        cod_m = int(row[col_cod_muni]) if col_cod_muni and not pd.isna(row[col_cod_muni]) else 0
                        unidad = str(row[col_unidades]) if col_unidades and not pd.isna(row[col_unidades]) else "HECTAREA"
                        
                        # Filtro Regional: Solo Valle (76) o Jamundi (76364)
                        if cod_d == 76:
                            event_fingerprint = self._generate_fingerprint("ASPERSION", row, fecha_obj.isoformat(), str(cod_m))
                            
                            yield {
                                "fuente_type": "TERRITORIAL_CONTEXT",
                                "source_id": "ASPERSION", # Legacy support
                                "fuente_id": "ASPERSION",
                                "departamento": str(dept),
                                "municipio": str(municipio),
                                "codigo_muni": cod_m,
                                "codigo_depto": cod_d,
                                "fecha_hecho": fecha_obj,
                                "anio": fecha_obj.year,
                                "mes": fecha_obj.month,
                                "cantidad": cantidad_val,
                                "unidad_medida": unidad,
                                "fuente_archivo": filename,
                                "event_fingerprint": event_fingerprint,
                                "hash_registro": event_fingerprint # Legacy support
                            }
                        continue

                    # --- LÓGICA ORIGINAL PARA CRIMEN ---
                    # Extraer discriminadores para el hash
                    sexo = str(row[col_sexo]) if col_sexo and not pd.isna(row[col_sexo]) else ""
                    zona = str(row[col_zona]) if col_zona and not pd.isna(row[col_zona]) else ""
                    edad = str(row[col_edad]) if col_edad and not pd.isna(row[col_edad]) else ""
                    mod = str(row[col_modalidad]) if col_modalidad and not pd.isna(row[col_modalidad]) else ""
                    
                    # Fuerza Pública
                    fuerza = str(row[col_fuerza]) if col_fuerza and not pd.isna(row[col_fuerza]) else ""
                    acc = str(row[col_accion]) if col_accion and not pd.isna(row[col_accion]) else ""
                    cat_grado = str(row[col_categoria]) if col_categoria and not pd.isna(row[col_categoria]) else ""
                    cod_dane = str(row[col_codigo_dane]) if col_codigo_dane and not pd.isna(row[col_codigo_dane]) else ""
                    
                    # Búsqueda de Barrio (para SEM)
                    col_barrio = next((c for c in header_vals if "BARRIO" in c), None)
                    barrio_raw = str(row[col_barrio]) if col_barrio and not pd.isna(row[col_barrio]) else ""

                    # Generar hash e importar si es necesario
                    
                    # Validación Jamundí Extendida
                    es_jamundi = "JAMUNDI" in municipio_norm or cod_dane == "76364"
                    if es_jamundi:
                        current_source_id = self._infer_crime_type_id(filename)
                        event_fingerprint = self._generate_fingerprint(current_source_id, row, fecha_obj.isoformat(), cod_dane)
                        
                        # Extraer Semana para SEM
                        semana_val = None
                        if "NOSEMANA" in header_vals:
                            semana_val = row["NOSEMANA"]
                        elif "SEMANA" in header_vals:
                            semana_val = row["SEMANA"]

                        yield {
                            "source_id": self._infer_crime_type_id(filename),
                            "departamento": str(dept) if not pd.isna(dept) else "VALLE DEL CAUCA",
                            "municipio": str(municipio),
                            "municipio_normalizado": municipio_norm,
                            "barrio": str(barrio_raw) if barrio_raw else None,
                            "fecha_hecho": fecha_obj,
                            "anio": fecha_obj.year,
                            "mes": fecha_obj.month,
                            "semana": int(semana_val) if semana_val and not pd.isna(semana_val) else None,
                            "tipo_delito": str(row.get("DESCRIPCION_CONDUCTA", tipo_delito)),
                            "cantidad": int(cantidad_val),
                            "genero": sexo,
                            "grupo_etario": edad,
                            "modalidad": mod,
                            "institucion": fuerza,
                            "accion": acc,
                            "categoria_grado": cat_grado,
                            "codigo_dane": cod_dane or ("76364" if "JAMUNDI" in municipio_norm else None),
                            "fuente_archivo": filename,
                            "event_fingerprint": event_fingerprint,
                            "hash_registro": event_fingerprint, # Legacy support
                            "fecha_ingesta": datetime.utcnow()
                        }
                    else:
                        # Modo Estricto: Ignoramos el resto del país para evitar Error 500 por OOM
                        continue

                except Exception as row_err:
                    logger.warning(f"Error procesando fila en {filename}: {row_err}")
                    continue

            # Bloque de agregación nacional removido para optimización
            pass
                    
        except Exception as e:
            logger.error(f"Error general procesando Excel {filename}: {e}")

    def _extract_year_from_filename(self, filename: str) -> int:
        import re
        match = re.search(r'20\d{2}', filename)
        # Default a 2025 si no se encuentra en el nombre, 
        # mejor que usar datetime.now() que daría 2026 por ahora.
        return int(match.group(0)) if match else 2025

    def _parse_date_openpyxl(self, date_val) -> date:
        if isinstance(date_val, (datetime, pd.Timestamp, date)):
            if hasattr(date_val, 'date') and callable(date_val.date):
                return date_val.date()
            return date_val
        if isinstance(date_val, str):
            try:
                # pandas to_datetime is very robust for strings like '01/01/2025'
                return pd.to_datetime(date_val, dayfirst=True).date()
            except:
                pass
        return None

    def _infer_crime_type(self, filename: str) -> str:
        name = self.normalize_text(filename).upper()
        if "ASPERSION" in name: return "ASPERSION"
        if "HOMICIDIO INTENCIONAL" in name: return "Homicidio Intencional"
        if "HOMICIDIO ACCIDENTES" in name: return "Homicidio (Tránsito)"
        if "LESIONES COMUNES" in name: return "Lesiones Personales"
        if "LESIONES ACCIDENTES" in name: return "Lesiones (Tránsito)"
        if "HURTO PERSONAS" in name: return "Hurto Personas"
        if "HURTO COMERCIO" in name: return "Hurto Comercio"
        if "HURTO RESIDENCIAS" in name: return "Hurto Residencias"
        if "HURTO VEHICULOS" in name: return "Hurto Vehículos"
        if "EXTORSION" in name: return "Extorsión"
        if "SECUESTRO" in name: return "Secuestro"
        if "SEXUALES" in name: return "Delitos Sexuales"
        if "INTRAFAMILIAR" in name: return "Violencia Intrafamiliar"
        if "TERRORISMO" in name: return "Terrorismo"
        if "MEDIO AMBIENTE" in name: return "Delitos Ambientales"
        if "INFORMATICOS" in name: return "Delitos Informáticos"
        if "MASACRES" in name: return "Masacres"
        if "HOMICIDIO" in name: return "Homicidio"
        if "HURTO" in name: return "Hurto"
        if "AFECTACION" in name: return "Afectación Fuerza Pública"
        if "RNMC" in name or "MEDIDAS GESTIONADAS" in name: return "RNMC (Medidas Gestionadas)"
        return "Delito General"
