from services.scraper_policia import PoliciaScraper

scraper = PoliciaScraper()
files = scraper.fetch_available_files()

print("Archivos disponibles de la Policia:")
for f in files:
    print(f"- {f['name']} (Año: {f.get('year')}) -> {f['url']}")
