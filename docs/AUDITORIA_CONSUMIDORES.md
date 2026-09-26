# Auditoría consumidores — cálculo único (metodología v1)

Fecha: 2026-09-08. Criterio: ¿la cifra oficial proviene del servicio común?

## Backend

| Consumidor | Archivo:línea | Regla usada | Veredicto |
|---|---|---|---|
| Indicador único | `services/indicator_calculation.py::calculate_indicator` | `COUNT DISTINCT hecho_key` para HECHO; `COUNT` identificable para VICTIMA | **Fuente de verdad** |
| Catálogo | `services/indicator_catalog.py` | HOMICIDIO=HECHO (pendiente firma Observatorio), HOMICIDIO_VICTIMAS=VICTIMA | OK, dual sin mezclar |
| Chat titular | `api/ia.py:775-830` | Llama a `calculate_indicator` para total/homicidios; prevalece servicio común; devuelve `provenance {unit, period, source_version_id, methodology_version, query_hash}` | **Integrado** |
| Chat desgloses | `api/ia.py:800-950` | `hechos_unicos_expr()` para anuales/mensuales; legacy `Event COUNT` solo como respaldo etiquetado; snapshot usa `COUNT DISTINCT hecho_key` | OK, etiquetar fuente en respuesta |
| Explorer policial | `api/ingesta.py:479-502` | Corregido a `hechos_unicos_expr()` + `unit=HECHO, methodology_version=1` | **Corregido en esta validación** |
| Tablero público | `api/analitica.py:200,239,250` | `COUNT DISTINCT identity_expr` / `hechos_unicos_expr()` | OK (misma regla) |
| Boletín | `services/sisc_cifras_service.py::police_indicators` | `hechos_unicos_expr()` | OK |
| PDF | `services/sisc_cifras_pdf.py` ← `publication_json` guardada | Muestra publicación guardada, no recalcula | OK si se publica versión fijada |
| Alertas | `services/alert_rules.py::evaluate_weekly/emit_weekly` + `GET /api/ia/alertas-semanales` | Ventanas [inicio, fin) 7vs7, cobertura completa anclada al corte, cero vs ausencia, cálculo único con entrega fija, evidencia + `dedupe_key` idempotente | **Integrado (HOMICIDIO)**; legado `AlertEngine` solo compatibilidad |
| Alertas legado | `services/alert_engine.py:53-92` (`GET /api/ia/alertas`) | Mezcla `COUNT(Event)` legacy + `hechos_unicos` moderno; ventanas 8 vs 7 días; `pre=0` → 100% semanal pero 0% mensual; no distingue cero vs sin datos | **No usar para decisiones**; reemplazar tras acordar umbrales |
| Conciliación | `services/reconciliation_service.py` + `POST /reconcile` | Compara entregas centrales, mismos filtros/metodología | **Integrado** |

## Frontend (`plataforma-seguridad`)

| Flujo | Estado |
|---|---|
| `Dashboard.tsx:802-874` (`current++`, `counts[val]++`) | **NO oficial**: volumen de archivo Excel. No eliminado (útil como previsualización), pero debe etiquetarse y no publicarse. `fetchOfficialIndicator` existe en `lib/officialStats.ts` con **0 usos** — pendiente cablear totales oficiales. |
| `Dashboard.tsx:231,252` (`sisc_boletines_historial` localStorage) | **NO es historial oficial**. Pendiente importación (ver punto 5). |
| Boletín/PDF frontend | Debe renderizar `publication_json` del backend + `pdf_sha256`. Verificar que no re-sume Excel para el PDF oficial. |
| Conciliación frontend | Debe llamar `POST /reconcile`; el motor local solo sirve como borrador. |

## Respuesta reconocible (contrato)

Toda cifra oficial debe poder explicar: `indicator, unit/unit_code, period, source_version_id, methodology_version, query_hash, quality_status, reproducible/exploratory`.
`calculate_indicator` ya lo devuelve; chat lo expone en `provenance`; explorer en `summary`.
