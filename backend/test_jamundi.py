from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import time

url = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx"

print("Iniciando test de parseo y extraccion Jamundi...")
scraper = MinDefensaScraper()
processor = NationalStatsProcessor()

content = scraper.download_file(url)
if content:
    print(f"Éxito descargando: {len(content)} bytes")
    records = list(processor.process_excel(content, "HOMICIDIO INTENCIONAL.xlsx", "HOMICIDIO INTENCIONAL"))
    print(f"Total registros extraidos nacional: {len(records)}")
    
    jamundi_recs = [r for r in records if "JAMUND" in r['municipio_normalizado'].upper()]
    print(f"Registros exactos para Jamundí: {len(jamundi_recs)}")
    for r in jamundi_recs[:5]:
        print(f"  - {r}")
else:
    print("Retornó None")
