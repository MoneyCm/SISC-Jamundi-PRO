# Validación Observatorio — Unidad del indicador de homicidio

**Estado: PENDIENTE DE FIRMA.** Staging y pruebas técnicas pueden continuar; no publicar como oficial hasta firmar.

## 1. Indicadores

| Campo | HOMICIDIO (propuesto oficial) | HOMICIDIO_VICTIMAS (complementario) |
|---|---|---|
| Código | `HOMICIDIO` | `HOMICIDIO_VICTIMAS` |
| Nombre | Homicidio — hechos registrados | Homicidio — víctimas |
| Fuente | `POLICIA_SEMANAL` (SIEDCO/PONAL) | `POLICIA_SEMANAL` |
| Unidad estadística | **HECHO** | **VICTIMA** |
| Etiqueta pública | `hechos registrados` | `víctimas` |
| Regla conteo | `COUNT DISTINCT canonical_hecho_key(id_fuente, fingerprint, id)` | `COUNT` filas con persona identificable (+ `cantidad` si la fuente agrega) |
| Fecha utilizada | `fecha_evento` | `fecha_evento` |
| Territorio | `JAMUNDI` | `JAMUNDI` |
| Metodología vigente | `1` | `1` |

## 2. Regla para múltiples víctimas de un mismo hecho

- Mismo `HECHOS_ID` con N filas/víctimas = **1 hecho** en `HOMICIDIO`, **N víctimas** en `HOMICIDIO_VICTIMAS`.
- Ejemplo: hecho `H-1` con 3 víctimas → `HOMICIDIO=1`, `HOMICIDIO_VICTIMAS=3`, `POLICIA_REGISTROS=3`.
- Sin `HECHOS_ID` oficial: fallback a fingerprint (hecho+víctima), confianza `UNCERTAIN`. No presentar coincidencia aproximada como corrección confirmada.

## 3. Correspondencia con la fuente

- La sábana policial entrega **filas** (registro/víctima), no un total pre-agregado.
- La cifra institucional `HOMICIDIO` **no equivale** al número de filas del Excel.
- La plataforma que recuenta filas (`Dashboard.tsx counts[val]++`) muestra volumen de archivo, nunca cifra oficial.

## 4. Validación

- [ ] Responsable Observatorio: ____________________
- [ ] Fecha: ____________________
- [ ] Decisión: HECHO / VICTIMA / AMBOS (tachar lo que no aplique)
- [ ] Si cambia la regla respecto a metodología `1`, abrir metodología `2` (no reescribir historia).

## 5. Implementación técnica (ya lista para ambas decisiones)

- `backend/services/indicator_catalog.py::INDICATOR_CATALOG`
- `backend/services/indicator_calculation.py::calculate_indicator`
- `POST /api/sisc-cifras/indicator` con `methodology_version`, `source_version_id`, `query_hash`.
- Si el Observatorio elige VICTIMA como cifra principal, el código cambia sin mezclar conceptos y con nueva versión metodológica.
