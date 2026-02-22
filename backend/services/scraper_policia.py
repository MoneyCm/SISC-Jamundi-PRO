import requests
import urllib3
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class PoliciaScraper:
    BASE_URL = "https://www.policia.gov.co"
    SOURCE_URL = "https://www.policia.gov.co/index.php/estadistica-delictiva-old"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.BASE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        })
        self.session.verify = False

    def fetch_available_files(self) -> List[Dict]:
        """
        Extrae los enlaces directos a los archivos Excel desde la página principal de estadística.
        """
        files = []
        try:
            response = self.session.get(self.SOURCE_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Buscar todos los enlaces
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                if href.lower().endswith('.xlsx') or href.lower().endswith('.xls'):
                    # Parsear la URL completa por si es relativa
                    full_url = urljoin(self.BASE_URL, href)

                    file_name = full_url.split('/')[-1]
                    
                    # Evitar duplicados
                    if not any(f['url'] == full_url for f in files):
                        files.append({
                            "name": file_name,
                            "category": "Estadística Consolidada",
                            "url": full_url,
                            "year": self._infer_year(file_name),
                            "type": "excel"
                        })
                        logger.info(f"Archivo registrado (Policía): {file_name}")
                        
        except Exception as e:
            logger.error(f"Error extrayendo enlaces de la Policía Nacional: {e}")
            
        return files

    def download_file(self, url: str) -> Optional[bytes]:
        """
        Descarga el archivo desde una URL dada de la Policía Nacional.
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            logger.info(f"Descarga exitosa desde Policía Nacional: {len(response.content)} bytes")
            return response.content
        except Exception as e:
            logger.error(f"Error descargando el archivo {url}: {e}")
            return None

    def _infer_year(self, filename: str) -> int:
        import re
        match = re.search(r'20\d{2}', filename)
        if match:
            return int(match.group(0))
        return 2024 # Default prudente

# Para facilitar testing rápido
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    scraper = PoliciaScraper()
    archivos = scraper.fetch_available_files()
    for o in archivos:
        print(o['name'], "->", o['url'])
