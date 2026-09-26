import psycopg2, json

conn = psycopg2.connect(host='db', dbname='sisc_jamundi', user='sisc_user', password='sisc_password')
cur = conn.cursor()

conciliacion = {
    "period": {"start": "2024-01-01", "end": "2024-12-31"},
    "hechos_por_fuente": {
        "POLICIA_SEMANAL": {"hechos": 0, "source_version_id": "438e1090-7e2a-497c-ae89-a67f8c4bbb0b", "estado": "FIXED"},
        "FISCALIA_SPOA_V3": {"hechos": 1, "source_version_id": "3102458a-52e2-4cf4-9b54-6d9836691dfe", "estado": "FIXED"},
        "MEDICINA_LEGAL": {"hechos": 113, "source_version_id": "7389ace6-11c0-41f2-9383-7859c0834975", "estado": "FIXED"}
    },
    "pares": [
        {"par": "POLICIA-SPOA", "fuente_a": "POLICIA_SEMANAL", "fuente_b": "FISCALIA_SPOA_V3", "hechos_a": 0, "hechos_b": 1, "diferencia": 1, "dentro_umbral": True},
        {"par": "POLICIA-INMLCF", "fuente_a": "POLICIA_SEMANAL", "fuente_b": "MEDICINA_LEGAL", "hechos_a": 0, "hechos_b": 113, "diferencia": 113, "dentro_umbral": False},
        {"par": "SPOA-INMLCF", "fuente_a": "FISCALIA_SPOA_V3", "fuente_b": "MEDICINA_LEGAL", "hechos_a": 1, "hechos_b": 113, "diferencia": 112, "dentro_umbral": False}
    ],
    "estado": "WARNING",
    "arbitraje_forense": {"usado_inmlcf": True, "desempate": {"fuente_final": "MEDICINA_LEGAL", "razon": "Las tres capas divergen; INMLCF definitivo es la referencia forense."}},
    "evidencias": ["POLICIA-INMLCF: 0 vs 113 (diferencia 113 mayor que 1).", "SPOA-INMLCF: 1 vs 113 (diferencia 112 mayor que 1)."],
    "nota_metodologica": "Las capas no se suman: un mismo homicidio puede constar en Policia, Fiscalia e INMLCF. Todas cuentan HECHOS unicos. INMLCF (definitivas) arbitra el desempate forense sin sustituir la fuente declarada.",
    "methodology_version": "1"
}

cur.execute("""
    UPDATE sisc_cifras_publications SET publication_json = jsonb_set(
      publication_json,
      '{governance}',
      (publication_json->'governance') || (%s::jsonb)
    ) WHERE status = 'PUBLISHED';
""", (json.dumps({"integrity": {"tri_fuente_homicidios": conciliacion}}),))
conn.commit()
print("OK: tri_fuente_homicidios actualizado en publication_json (psycopg2)")
cur.close()
conn.close()
