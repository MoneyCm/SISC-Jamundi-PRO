from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import time

url = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx"

print("Iniciando test de timeout y parseo...")
t0 = time.time()
scraper = MinDefensaScraper()
processor = NationalStatsProcessor()

content = scraper.download_file(url)
t1 = time.time()
print(f"Descargado en {t1 - t0} s")

if content:
    print(f"Éxito: {len(content)} bytes")
    t2 = time.time()
    records = list(processor.process_excel(content, "HOMICIDIO INTENCIONAL.xlsx"))
    t3 = time.time()
    print(f"Parseo listo en {t3 - t2} s, {len(records)} registros generados.")
else:
    print("Retornó None")
