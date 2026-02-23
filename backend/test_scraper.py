import sys, os
sys.path.append(os.path.abspath('.'))
from services.scraper_mindefensa import MinDefensaScraper
print("Starting scraper test")
s = MinDefensaScraper()
try:
    print("Fetching files list...")
    files = s.fetch_available_files()
    print("Fetched", len(files), "files")
    if files:
        f = files[0]
        print("Downloading", f['url'])
        content = s.download_file(f['url'])
        if content:
            print("Downloaded", len(content), "bytes")
        else:
            print("Download failed, returned None")
except Exception as e:
    print("Exception occurred:", e)
