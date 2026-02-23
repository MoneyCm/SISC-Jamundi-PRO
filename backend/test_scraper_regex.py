import requests
import re
import urllib3
urllib3.disable_warnings()
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
try:
    r = requests.get("https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica", headers=headers, verify=False, timeout=30)
    html = r.text
    print("HTML length:", len(html))
    links = re.findall(r'href=[\"\'\s](.*?\.xlsx)[\"\'\s]', html, re.I)
    if not links:
        links = re.findall(r'[\"\'\s](.*?\.xlsx)[\"\'\s]', html, re.I)
    print("Found xlsx links:", len(links))
    for idx, l in enumerate(links[:20]):
        print(f"{idx}: {l}")
        
    print("\nAlso checking JSON/JS structures for APIs or JSON data:")
    if "api/v1.1/assets" in html:
        print("Found 'api/v1.1/assets' base URLs!")
    
except Exception as e:
    print("Exception:", e)
