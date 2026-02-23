import logging
import datetime
logging.basicConfig(level=logging.DEBUG)
from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor

def get_homicidios():
    scraper = MinDefensaScraper()
    processor = NationalStatsProcessor()
    
    url = scraper.KNOWN_URLS["HOMICIDIO INTENCIONAL"]
    print(f"Downloading {url} ...")
    content = scraper.download_file(url)
    
    if content:
        print("Processing...")
        gen = processor.process_excel(content, "HOMICIDIO INTENCIONAL.xlsx")
        
        c = 0
        for r in gen:
            print(f"[{c}] Municipio: {r['municipio']}, Fecha: {r['fecha_hecho']} (Año: {r['anio']}, Mes: {r['mes']}), Cant: {r['cantidad']}")
            c += 1
            if c > 20: break
    else:
        print("Failed to download")

if __name__ == "__main__":
    get_homicidios()
