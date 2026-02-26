## Exportación avanzada de alertas RNMC

### 1. Excel de ranking

**Endpoint**

- `GET /api/intelligence/alerts/export/excel`

**Parámetros principales (query)**

- `source` (opcional, por defecto `RNMC`)
- `status` (opcional, por defecto `OPEN`)
- `tier` (opcional, puede ser `P1`, `P2`, `P3` o una lista separada por comas, por ejemplo `P1,P2`)
- `from` (opcional, `YYYY-MM-DD`)
- `to` (opcional, `YYYY-MM-DD`)
- `limit` (opcional, por defecto `500`, máximo `1000`)

**Ejemplo curl**

```bash
curl -X GET "http://localhost:8000/api/intelligence/alerts/export/excel?source=RNMC&status=OPEN&tier=P1,P2&limit=500" \
  -H "Authorization: Bearer <TOKEN_JWT>" \
  -o alerts_rnmc.xlsx
```

**Contenido del XLSX**

- Hoja `Ranking`: filas con columnas
  - `created_at, updated_at, source, alert_type, severity, priority_tier, action_score, dias, valor_neto, valor_pagado, estado, localidad, medida, source_id, event_fingerprint, recommended_action, rationale_md`
- Hoja `Summary`: métricas agregadas
  - Conteos por tier/severidad, `Valor neto P1 sin pago`, `Recaudo total (valor_pagado)`
- Hoja `Config`: configuración de scoring usada
  - `MAX_DIAS, MAX_VALOR, W_AGE, W_VALUE, W_STATE, W_ZONE, P1_THRESHOLD, P2_THRESHOLD`
  - `scoring_config_sha256`, `generated_at_utc`, filtros básicos (`source`, `status`, `tiers`, `from`, `to`)

---

### 2. CSV de ranking

**Endpoint**

- `GET /api/intelligence/alerts/export/csv`

Mismos parámetros que el Excel. Ejemplo:

```bash
curl -X GET "http://localhost:8000/api/intelligence/alerts/export/csv?source=RNMC&status=OPEN&tier=P1&limit=200" \
  -H "Authorization: Bearer <TOKEN_JWT>" \
  -o alerts_rnmc.csv
```

---

### 3. Snapshot de ranking (JSON en DB)

**Endpoint**

- `POST /api/intelligence/alerts/snapshot`

**Body (JSON)**

```json
{
  "source": "RNMC",
  "status": "OPEN",
  "tiers": ["P1", "P2"],
  "severity": null,
  "from_date": null,
  "to_date": null,
  "limit": 500
}
```

**Ejemplo curl**

```bash
curl -X POST "http://localhost:8000/api/intelligence/alerts/snapshot" \
  -H "Authorization: Bearer <TOKEN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"source":"RNMC","status":"OPEN","tiers":["P1","P2"],"limit":500}'
```

**Respuesta**

```json
{
  "snapshot_id": "1f5e3c9a-8a72-4f25-8e9d-9b3b4f2f1c10",
  "sha256": "b0f5e0d4b0d5c3ffa9a1e7b8a4bd3bdbb5f1d03a9c6fbe4a3e5f7e9d2c4b1f0",
  "created_at": "2026-02-26T15:30:12.123456",
  "source": "RNMC"
}
```

**Tabla asociada**

- `intelligence_alert_snapshots`
  - `id` (UUID, PK)
  - `created_at` (timestamptz)
  - `source` (text)
  - `filters` (jsonb)
  - `scoring_config` (jsonb)
  - `payload_json` (jsonb, lista de alertas sin PII)
  - `payload_sha256` (text, UNIQUE)

**Verificación del hash (ejemplo)**

1. Exportar el `payload_json` del snapshot (por SQL o herramienta).
2. Guardarlo como `payload.json` con ordenamiento estable (opcional).
3. Ejecutar:

```bash
sha256sum payload.json
```

4. Comparar la salida con el campo `payload_sha256` devuelto por la API.

---

### 4. PDF ejecutivo on-demand

**Endpoint**

- `POST /api/intelligence/alerts/export/pdf`

**Body (JSON)**

Dos modos:

1. **Usando filtros (crea un snapshot nuevo internamente):**

```json
{
  "source": "RNMC",
  "status": "OPEN",
  "tiers": ["P1", "P2"],
  "severity": null,
  "from_date": null,
  "to_date": null,
  "limit": 500
}
```

2. **Usando un `snapshot_id` existente:**

```json
{
  "snapshot_id": "1f5e3c9a-8a72-4f25-8e9d-9b3b4f2f1c10"
}
```

**Ejemplo curl (PDF directo)**

```bash
curl -X POST "http://localhost:8000/api/intelligence/alerts/export/pdf" \
  -H "Authorization: Bearer <TOKEN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"source":"RNMC","status":"OPEN","tiers":["P1","P2"],"limit":500}' \
  -o alerts_rnmc_ejecutivo.pdf
```

**Contenido del PDF**

- Header: periodo (a partir de filtros), fecha de generación, fuente RNMC.
- KPIs:
  - Total alertas
  - #P1 / #P2 / #P3
- Tabla `Top 10 P1`:
  - `localidad, medida, días, valor_neto, score, razón corta`
- Resumen de cartera:
  - `Monto neto P1 sin pago`
  - Top localidades por número de P1.
- **Sello de evidencia**:
  - `Snapshot ID`
  - `Payload SHA256`
  - `Scoring config hash`

---

### 5. Migración / creación de tabla de snapshots

Para asegurar la tabla `intelligence_alert_snapshots` en cualquier entorno:

```bash
cd backend
python db/migrate_alert_snapshots.py
```

Esto usa `SQLALCHEMY_DATABASE_URL` y `Base.metadata.create_all` sólo para esa tabla.

---

### 6. Pruebas de scoring (pytest)

**Archivo**

- `backend/tests/test_alert_prioritization.py`

**Pruebas clave**

- `test_tier_boundaries`: verifica fronteras de tiers usando el score redondeado:
  - `74.99 => P2`
  - `75.00 => P1`
  - `44.99 => P3`
  - `45.00 => P2`
- `test_idempotent_scoring`: misma alerta + misma configuración ⇒ mismo `action_score`, `priority_tier`, `recommended_action`, `rationale_md`.
- `test_zone_optional_neutral`: sin `zone_score` en métricas ⇒ uso neutral (0.5) y sin errores.

**Ejecución local (dentro de venv con pytest instalado)**

```bash
cd backend
pytest -q tests/test_alert_prioritization.py
```

