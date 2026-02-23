import requests

def test_ingest():
    print("Triggering ingestion via /api/intelligence/ingest ...")
    resp = requests.post("http://localhost:8000/api/intelligence/ingest")
    print(resp.status_code, resp.text)

if __name__ == "__main__":
    test_ingest()
