import requests
import urllib3
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Disable insecure request warnings since we use verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("sisc_api")

class MinDefensaScraper:
    BASE_URL = "https://www.mindefensa.gov.co"
    SOURCE_URL = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    
    # Mapeo de URLs finales directas (requieren cookie siteId=Sitio-Web-Ministerio-Defensa y Referer)
    KNOWN_URLS = {
        "HOMICIDIO INTENCIONAL": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx",
        "HOMICIDIO ACCIDENTES": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD456E9301E634D93ACBCF54B70942138/native/HOMICIDIO%20ACCIDENTES%20DE%20TR\u00c1NSITO.xlsx",
        "LESIONES COMUNES": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT53C09FE87BE14ACE904069DB6848C811/native/LESIONES%20COMUNES.xlsx",
        "LESIONES ACCIDENTES": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT4DA40868407D4752B24BE742D8BF0452/native/LESIONES%20ACCIDENTES%20DE%20TR\u00c1NSITO.xlsx",
        "HURTO PERSONAS": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTEBDF030F568F49A4A73563ADB8DBA8AB/native/HURTO%20PERSONAS.xlsx",
        "HURTO A COMERCIO": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT1F6023E051B746DAA1F3E4075209A882/native/HURTO%20A%20COMERCIO.xlsx",
        "HURTO A RESIDENCIAS": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT278B01DD860B435DB5ECC2AB6ABC3EDB/native/HURTO%20A%20RESIDENCIAS.xlsx",
        "EXTORSIÓN": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT7154F2FB1B264CDCAD9A48A3BEE58A77/native/EXTORSI\u00d3N.xlsx",
        "HURTO DE VEHÍCULOS": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT2BF65517CF044CC19DD6CB5BB4A7B411/native/HURTO%20DE%20VEH\u00cdCULOS.xlsx",
        "HURTO ABIGEATO": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTA10A2B7AA8244E908DE49ADC66350C71/native/HURTO%20ABIGEATO.xlsx",
        "HURTO ENTIDADES FINANCIERAS": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT253B6D0EC16D4FC58A6A28EE5C40634E/native/HURTO%20ENTIDADES%20FINANCIERAS.xlsx",
        "SECUESTRO": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTDC54E523A2BA492AA1C57065A0D3C6D8/native/SECUESTRO.xlsx",
        "DELITOS SEXUALES": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTEBEA4A10A270484195D139CF815742F3/native/DELITOS%20SEXUALES.xlsx",
        "VIOLENCIA INTRAFAMILIAR": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT93A3E06E0C134EF197783385D56AABBF/native/VIOLENCIA%20INTRAFAMILIAR.xlsx",
        "TERRORISMO": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTDF4D607F36A147BBAD763111C365256E/native/TERRORISMO.xlsx",
        "DELITOS INFORMÁTICOS": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT92AC3B93285642069C008C997FA6F8DA/native/DELITOS%20INFORM\u00c1TICOS.xlsx",
        "MASACRES": "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT7B88CCACEDD441E3984D326E3696DB5E/native/MASACRES.xlsx"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": self.SOURCE_URL,
            "Connection": "keep-alive",
        })
        self.session.cookies.update({
            "siteId": "Sitio-Web-Ministerio-Defensa"
        })
        self.session.verify = False

    def fetch_available_files(self) -> List[Dict]:
        """
        Retorna archivos disponibles usando las URLs confirmadas.
        """
        files = []
        
        for name, url in self.KNOWN_URLS.items():
            files.append({
                "name": f"{name}.xlsx",
                "category": self._infer_category(name), 
                "url": url,
                "year": 2025,
                "type": "excel"
            })
            logger.info(f"Archivo registrado: {name}")

        return files

    def _parse_dynamic_content(self, html: str) -> List[Dict]:
        return []

    def _infer_category(self, name: str) -> str:
        name_upper = name.upper()
        if any(x in name_upper for x in ["HOMICIDIO", "LESIONES", "MASACRES"]): return "Vida e Integridad"
        if any(x in name_upper for x in ["HURTO", "EXTORSIÓN", "PIRATERÍA", "INVASIÓN"]): return "Patrimonio Económico"
        if any(x in name_upper for x in ["SECUESTRO", "TRATA"]): return "Libertad Individual"
        if any(x in name_upper for x in ["SEXUALES"]): return "Integridad Sexual"
        if any(x in name_upper for x in ["VIOLENCIA", "INTRAFAMILIAR"]): return "Familia"
        if any(x in name_upper for x in ["TERRORISMO", "OLEODUCTOS", "PUENTES"]): return "Seguridad Pública"
        if any(x in name_upper for x in ["MEDIO AMBIENTE", "MINERÍA", "MINAS"]): return "Medio Ambiente"
        if any(x in name_upper for x in ["INFORMÁTICOS"]): return "Delitos Cibernéticos"
        return "Delitos Generales"

    def _extract_year_from_filename(self, filename: str) -> int:
        match = re.search(r'20\d{2}', filename)
        return int(match.group(0)) if match else 2025

    def download_file(self, url: str) -> Optional[bytes]:
        try:
            resp = self.session.get(url, timeout=15.0)
            if resp.status_code == 200:
                return resp.content
            logger.warning(f"Error descargando {url}: Status {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Excepción descargando archivo {url}: {e}")
            return None
