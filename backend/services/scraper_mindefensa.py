import requests
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger("sisc_api")

class MinDefensaScraper:
    BASE_URL = "https://www.mindefensa.gov.co"
    SOURCE_URL = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    
    # Patrón para construir la URL de descarga basado en el contentId
    # Basado en la investigación, Oracle UCM suele usar /sites/[SiteName]/content/[ContentId]
    # O a veces requiere un token. Si el curl directo funciona, usamos ese.
    DOWNLOAD_TEMPLATE = "https://www.mindefensa.gov.co/sites/Sitio-Web-Ministerio-Defensa/content/{content_id}"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def fetch_available_files(self) -> List[Dict]:
        """
        Descarga el HTML de la página y extrae los metadatos de los archivos Excel disponibles.
        Retorna una lista de diccionarios con {name, year, url, description}.
        """
        try:
            response = self.session.get(self.SOURCE_URL, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            return self._parse_oracle_cms_data(html_content)
        except Exception as e:
            logger.error(f"Error accediendo a MinDefensa: {e}")
            return []

    def _parse_oracle_cms_data(self, html: str) -> List[Dict]:
        """
        Parsea el JSON incrustado en el HTML de Oracle WebCenter.
        Busca componentes que tengan referencias a archivos .xlsx
        """
        files = []
        
        # Estrategia: Buscar bloques JSON dentro de <script> o definidos en `pageData`
        # El HTML tiene un bloque grande `pageData: {...}` o `componentInstances: {...}`
        
        # Regex simplificado para encontrar objetos que parecen archivos Excel
        # Buscamos "imageHrefName":"...xlsx" y su "contentId" asociado
        # Ejemplo: "contentId":"CONT...", ..., "imageHrefName":"....xlsx"
        
        # Nota: El JSON es complejo, un regex simple puede ser frágil pero efectivo para empezar.
        # Buscamos patrones de objetos que tengan imageHrefName terminados en xlsx
        
        # Patrón para capturar bloques que contienen .xlsx
        # Ajustado para capturar el contentId cercano
        file_matches = re.finditer(r'"contentId":"(CONT[A-Z0-9]+)".*?"imageHrefName":"([^"]+\.xlsx)"', html, re.DOTALL)
        
        found_ids = set()
        
        for match in file_matches:
            content_id = match.group(1)
            file_name = match.group(2)
            
            if content_id in found_ids:
                continue
                
            found_ids.add(content_id)
            
            # Inferir año del nombre del archivo
            year = self._extract_year(file_name)
            
            files.append({
                "name": file_name,
                "content_id": content_id,
                "url": self.DOWNLOAD_TEMPLATE.format(content_id=content_id),
                "year": year,
                "type": "excel"
            })
            
        logger.info(f"Se encontraron {len(files)} archivos Excel en MinDefensa.")
        return files

    def _extract_year(self, filename: str) -> int:
        """Intenta extraer el año del nombre del archivo (ej. report_2025.xlsx)"""
        match = re.search(r'20\d{2}', filename)
        if match:
            return int(match.group(0))
        return datetime.now().year # Fallback

    def download_file(self, url: str) -> Optional[bytes]:
        try:
            resp = self.session.get(url, timeout=60)
            if resp.status_code == 200:
                return resp.content
            logger.warning(f"Error descargando {url}: Status {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Excepción descargando archivo: {e}")
            return None
