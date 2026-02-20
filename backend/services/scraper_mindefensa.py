import httpx
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

    CHANNEL_TOKEN = "CHANNELFF1A0283472D39BA01F73E8B55227A61E680A929CB63"

    # Mapeo de URLs estables capturadas (Endpoint Published + ChannelToken)
    KNOWN_URLS = {
        "HOMICIDIO INTENCIONAL": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx",
        "HOMICIDIO ACCIDENTES": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTD456E9301E634D93ACBCF54B70942138/native/HOMICIDIO%20ACCIDENTES%20DE%20TR\u00c1NSITO.xlsx",
        "LESIONES COMUNES": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT53C09FE87BE14ACE904069DB6848C811/native/LESIONES%20COMUNES.xlsx",
        "LESIONES ACCIDENTES": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT4DA40868407D4752B24BE742D8BF0452/native/LESIONES%20ACCIDENTES%20DE%20TR\u00c1NSITO.xlsx",
        "HURTO PERSONAS": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTEBDF030F568F49A4A73563ADB8DBA8AB/native/HURTO%20PERSONAS.xlsx",
        "HURTO A COMERCIO": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT1F6023E051B746DAA1F3E4075209A882/native/HURTO%20A%20COMERCIO.xlsx",
        "HURTO A RESIDENCIAS": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT278B01DD860B435DB5ECC2AB6ABC3EDB/native/HURTO%20A%20RESIDENCIAS.xlsx",
        "EXTORSIÓN": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT7154F2FB1B264CDCAD9A48A3BEE58A77/native/EXTORSI\u00d3N.xlsx",
        "HURTO DE VEH\u00cdCULOS": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT2BF65517CF044CC19DD6CB5BB4A7B411/native/HURTO%20DE%20VEH\u00cdCULOS.xlsx",
        "SECUESTRO": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTDC54E523A2BA492AA1C57065A0D3C6D8/native/SECUESTRO.xlsx",
        "DELITOS SEXUALES": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTEBEA4A10A270484195D139CF815742F3/native/DELITOS%20SEXUALES.xlsx",
        "VIOLENCIA INTRAFAMILIAR": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT93A3E06E0C134EF197783385D56AABBF/native/VIOLENCIA%20INTRAFAMILIAR.xlsx",
        "TERRORISMO": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONTDF4D607F36A147BBAD763111C365256E/native/TERRORISMO.xlsx",
        "DELITOS INFORM\u00c1TICOS": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT92AC3B93285642069C008C997FA6F8DA/native/DELITOS%20INFORM\u00c1TICOS.xlsx",
        "MEDIO AMBIENTE": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT8A90C91C09374BC0BBD44108E631B2B1/native/DELITOS%20CONTRA%20EL%20MEDIO%20AMBIENTE.xlsx",
        "MASACRES": "https://www.mindefensa.gov.co/sites/web/content/published/api/v1.1/assets/CONT7B88CCACEDD441E3984D326E3696DB5E/native/MASACRES.xlsx"
    }

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Referer": self.SOURCE_URL,
                "Connection": "keep-alive",
            },
            verify=False,
            timeout=120.0,
            follow_redirects=True,
            http2=False 
        )

    def fetch_available_files(self) -> List[Dict]:
        """
        Retorna archivos disponibles usando URLs estables con channelToken.
        """
        files = []
        
        for name, base_url in self.KNOWN_URLS.items():
            download_url = f"{base_url}?channelToken={self.CHANNEL_TOKEN}"
            files.append({
                "name": f"{name}.xlsx",
                "category": None, 
                "url": download_url,
                "year": 2025,
                "type": "excel"
            })
            logger.info(f"Archivo activado (URL Publicada + Token): {name}")

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
            resp = self.client.get(url)
            if resp.status_code == 200:
                return resp.content
            logger.warning(f"Error descargando {url}: Status {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Excepción descargando archivo {url}: {e}")
            return None
