import requests

url = "http://localhost:8000/api/analitica/estadisticas/distribucion?start_date=2026-01-01&end_date=2026-03-05&fuente=MINDEFENSA"
res = requests.get(url)
print("Status:", res.status_code)
try:
    print("JSON:", res.json())
except:
    print("Text:", res.text)
