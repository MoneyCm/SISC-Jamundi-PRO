import requests
import time
import hashlib
import os

def run_ingest(token, iteration, file_path):
    url = 'http://localhost:8000/api/intelligence/upload'
    
    with open(file_path, 'rb') as f:
        content = f.read()
        file_hash = hashlib.sha256(content).hexdigest()
        f.seek(0)
        
        start_time = time.time()
        headers = {'Authorization': f'Bearer {token}'}
        files = {'file': (os.path.basename(file_path), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        try:
            r = requests.post(url, files=files, headers=headers)
            duration = int((time.time() - start_time) * 1000)
            
            res = r.json()
            status_final = res.get("status", "FAILED")
            
            return {
                "corrida_n": iteration,
                "ingestion_id": res.get("ingestion_id"),
                "source_id": res.get("source_id"),
                "file_name": os.path.basename(file_path),
                "file_hash": res.get("file_hash"),
                "status_final": status_final,
                "inserted_count": res.get("inserted_count", 0),
                "updated_count": res.get("updated_count", 0),
                "skipped_count": res.get("skipped_count", 0),
                "periodo_detectado": res.get("periodo_detectado", res.get("periodo")),
                "api_message": res.get("message")
            }
        except Exception as e:
            return {"corrida_n": iteration, "status_final": "FAILED", "error": str(e)}

if __name__ == "__main__":
    # Obtener token
    resp = requests.post('http://localhost:8000/api/auth/login', data={'username': 'admin_sisc', 'password': 'admin_password'})
    token = resp.json().get('access_token')
    
    import sys
    it = int(sys.argv[1])
    f_path = sys.argv[2] if len(sys.argv) > 2 else r'c:\Users\USER\Downloads\AFECTACIÓN A LA FUERZA PÚBLICA.xlsx'
    print(run_ingest(token, it, f_path))
