from services.scraper_mindefensa import MinDefensaScraper
import time

url = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx"

print("Iniciando test de timeout...")
inicio = time.time()
scraper = MinDefensaScraper()
try:
    content = scraper.download_file(url)
    if content:
        print(f"Éxito: {len(content)} bytes")
    else:
        print("Retornó None (probablemente timeout capturado u otro error)")
except Exception as e:
    print(f"Excepción general: {e}")

print(f"Tiempo total: {time.time() - inicio} segundos")
