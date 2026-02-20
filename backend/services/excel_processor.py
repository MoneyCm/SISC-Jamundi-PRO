import pandas as pd
import unicodedata
import logging
from datetime import datetime, date
from typing import List, Dict, Generator
import io

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
        
        # Limpieza específica para municipios colombianos
        text = text.replace(", D.C.", "").replace(" D.C.", "")
        text = text.replace(".", "")
        return text

    def process_excel(self, file_content: bytes, filename: str, inferred_crime_type: str = None) -> Generator[Dict, None, None]:
        """
        Procesa el archivo Excel y genera diccionarios listos para insertar en DB.
        """
        try:
            # Leer excel en memoria
            xls = pd.ExcelFile(io.BytesIO(file_content))
            
            # Asumimos que la primera hoja tiene los datos relevantes
            # MinDefensa suele tener encabezados en filas 5-8. 
            # Estrategia robusta: buscar la fila donde empieza "DEPARTAMENTO" o "MUNICIPIO"
            df = pd.read_excel(xls, sheet_name=0, header=None)
            
            header_row_idx = self._find_header_row(df)
            if header_row_idx == -1:
                logger.error(f"No se encontró fila de encabezado en {filename}")
                return

            # Recargar con el encabezado correcto
            df = pd.read_excel(xls, sheet_name=0, header=header_row_idx)
            
            # Normalizar nombres de columnas
            df.columns = [self.normalize_text(str(c)) for c in df.columns]
            
            # Validar columnas mínimas
            required_cols = ["MUNICIPIO", "DEPARTAMENTO"]
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Faltan columnas requeridas en {filename}: {df.columns}")
                return
                
            # Identificar año del archivo o columnas de fecha
            # Si el archivo es multianual, debe tener columna FECHA o ANIO
            has_date_col = "FECHA" in df.columns
            file_year = self._extract_year_from_filename(filename)
            
            for _, row in df.iterrows():
                try:
                    municipio = row.get("MUNICIPIO")
                    if pd.isna(municipio) or municipio == "TOTAL":
                        continue
                        
                    dept = row.get("DEPARTAMENTO")
                    municipio_norm = self.normalize_text(municipio)
                    
                    # Determinar tipo de delito (Prioridad: Inferred > Filename)
                    tipo_delito = inferred_crime_type or self._infer_crime_type(filename)
                    
                    # Determinar fecha y año
                    if has_date_col:
                        fecha_raw = row.get("FECHA")
                        # Parsear fecha (asumiendo datetime o string)
                        fecha_obj = self._parse_date(fecha_raw)
                    else:
                        # Si no hay fecha exacta, asumimos por nombre de columna (ej: Enero, Febrero...)
                        # O si es consolidado anual, usamos 1ro de Enero
                        fecha_obj = date(file_year, 1, 1)

                    if not fecha_obj:
                        continue

                    # Extraer conteo (sumar columnas de delitos si hay desglose)
                    cantidad = row.get("CANTIDAD", 1) # Default 1 si es registro individual
                    if "TOTAL" in row:
                        cantidad = row["TOTAL"]
                    
                    # Generar hash único para evitar duplicados
                    import hashlib
                    hash_input = f"{municipio_norm}|{fecha_obj}|{tipo_delito}|{cantidad}"
                    registro_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                    
                    # Construir objeto
                    yield {
                        "departamento": str(dept),
                        "municipio": str(municipio),
                        "municipio_normalizado": municipio_norm,
                        "fecha_hecho": fecha_obj,
                        "anio": fecha_obj.year,
                        "mes": fecha_obj.month,
                        "tipo_delito": tipo_delito,
                        "cantidad": int(cantidad) if pd.notnull(cantidad) else 0,
                        "fuente_archivo": filename,
                        "hash_registro": registro_hash,
                        "fecha_ingesta": datetime.utcnow()
                    }
                    
                except Exception as row_err:
                    logger.warning(f"Error procesando fila en {filename}: {row_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error general procesando Excel {filename}: {e}")

    def _find_header_row(self, df) -> int:
        """Busca la fila que contiene 'MUNICIPIO'"""
        for i, row in df.iterrows():
            row_vals = [str(x).upper() for x in row.values]
            if "MUNICIPIO" in row_vals:
                return i
        return -1

    def _extract_year_from_filename(self, filename: str) -> int:
        import re
        match = re.search(r'20\d{2}', filename)
        # Default a 2025 si no se encuentra en el nombre, 
        # mejor que usar datetime.now() que daría 2026 por ahora.
        return int(match.group(0)) if match else 2025

    def _parse_date(self, date_val) -> date:
        if isinstance(date_val, (datetime, pd.Timestamp)):
            return date_val.date()
        if isinstance(date_val, str):
            try:
                return pd.to_datetime(date_val).date()
            except:
                pass
        return None # Dejar que el llamador lo maneje

    def _infer_crime_type(self, filename: str) -> str:
        name = self.normalize_text(filename).upper()
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
        return "Delito General"
