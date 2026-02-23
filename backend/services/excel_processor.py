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
        
        # Limpieza específica para municipios colombianos y formatos de archivo
        text = text.replace(", D.C.", "").replace(" D.C.", "")
        text = text.replace(".", "").replace("_", " ")
        return text

    def process_excel(self, file_content: bytes, filename: str, inferred_crime_type: str = None) -> Generator[Dict, None, None]:
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
            # Buscar en las primeras 20 filas la palabra MUNICIPIO como indicador de header
            for idx, row in df_raw.head(20).iterrows():
                row_str = [str(x).upper().strip() for x in row.values if pd.notna(x)]
                if any("MUNICIPIO" in v for v in row_str):
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
                "MUNICIPIO", "DEPARTAMENTO", 
                "FECHA", "CANTIDAD", "TOTAL", "VICTIMAS", "NUMERO_CASOS",
                "SEXO", "GENERO", "ZONA", "EDAD", "MODALIDAD", "ARMA", "MEDIO"
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
            
            # Identificar columnas
            col_municipio = "MUNICIPIO" if "MUNICIPIO" in header_vals else None
            col_depto = "DEPARTAMENTO" if "DEPARTAMENTO" in header_vals else None
            
            if not col_municipio or not col_depto:
                logger.error(f"Faltan columnas requeridas en {filename}: {header_vals}")
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

            file_year = self._extract_year_from_filename(filename)
            tipo_delito = inferred_crime_type or self._infer_crime_type(filename)
            
            # Modo Estricto Jamundí: No acumulamos datos nacionales por ahora para optimizar recursos
            # nacional_agg = {}

            # Iterar sobre las filas (mucho más seguro con iterrows)
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
                        fecha_obj = self._parse_date_openpyxl(fecha_raw) # Función reutilizada, maneja pd.Timestamp
                    
                    if not fecha_obj:
                        fecha_obj = date(file_year, 1, 1)

                    # Cantidad
                    cantidad = 1
                    if col_cantidad and not pd.isna(row[col_cantidad]):
                        try:
                            cantidad = int(float(row[col_cantidad]))
                        except (ValueError, TypeError):
                            pass

                    # Extraer discriminadores para el hash
                    sexo = str(row[col_sexo]) if col_sexo and not pd.isna(row[col_sexo]) else ""
                    zona = str(row[col_zona]) if col_zona and not pd.isna(row[col_zona]) else ""
                    edad = str(row[col_edad]) if col_edad and not pd.isna(row[col_edad]) else ""
                    mod = str(row[col_modalidad]) if col_modalidad and not pd.isna(row[col_modalidad]) else ""
                    
                    # Generar hash e importar si es necesario
                    import hashlib
                    
                    if "JAMUNDI" in municipio_norm:
                        # Registro determinístico para evitar duplicados en re-ingestas
                        # Incluimos discriminadores para evitar colisiones en filas "idénticas" de un mismo archivo
                        hash_input = f"{tipo_delito}|{filename}|{dept}|{municipio_norm}|{fecha_obj.isoformat()}|{cantidad}|{sexo}|{zona}|{edad}|{mod}"
                        registro_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                        
                        yield {
                            "departamento": str(dept) if not pd.isna(dept) else "",
                            "municipio": str(municipio),
                            "municipio_normalizado": municipio_norm,
                            "fecha_hecho": fecha_obj,
                            "anio": fecha_obj.year,
                            "mes": fecha_obj.month,
                            "tipo_delito": tipo_delito,
                            "cantidad": cantidad,
                            "genero": sexo,
                            "grupo_etario": edad,
                            "modalidad": mod,
                            "fuente_archivo": filename,
                            "hash_registro": registro_hash,
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
