
import hashlib
import datetime

def generate_hash(tipo_delito, filename, dept, municipio_norm, fecha_obj, cantidad):
    hash_input = f"{tipo_delito}|{filename}|{dept}|{municipio_norm}|{fecha_obj.isoformat()}|{cantidad}"
    return hashlib.sha256(hash_input.encode()).hexdigest()

# Simulate two runs with the same data
data = {
    "tipo_delito": "Homicidio Intencional",
    "filename": "HOMICIDIO_INTENCIONAL.xlsx",
    "dept": "VALLE DEL CAUCA",
    "municipio_norm": "JAMUNDI",
    "fecha_obj": datetime.date(2025, 1, 1),
    "cantidad": 5
}

hash1 = generate_hash(**data)
hash2 = generate_hash(**data)

print(f"Hash 1: {hash1}")
print(f"Hash 2: {hash2}")

if hash1 == hash2:
    print("SUCCESS: Hashes are identical for identical data (idempotent).")
else:
    print("FAILURE: Hashes differ for identical data.")
