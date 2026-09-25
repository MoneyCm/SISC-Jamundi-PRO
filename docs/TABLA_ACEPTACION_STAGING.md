# Aceptación staging — resultado esperado inequívoco (metodología v1 propuesta)

Periodo: `2026-07-01 a 2026-07-05`. Territorio: `JAMUNDI`. Fuente: `POLICIA_SEMANAL`.
(El corte de la entrega A es 2026-07-05; publicar hasta el corte deja cobertura `aligned`.)

## Entregas controladas

- **A**: H-1 (HOMICIDIO, barrio A) ×3 víctimas + H-2 (HURTO, barrio X). Es decir: 4 registros, 2 hechos.
- **B**: H-1 ×2 víctimas (falta 1: archivo incremental, ausente≠eliminado) + H-2 corregido (barrio Y) y reclasificado (HURTO→LESIONES) + H-3 (HURTO, barrio Z, **retrospectivo 2026-07-04** dentro del periodo).

## Tabla de aceptación

| Consulta (indicador, filtros, unidad) | Entrega A — valor esperado | Entrega B — valor esperado | Diferencia esperada |
|---|---|---|---|
| `SEGURIDAD_TOTAL`, 2026-07-01–2026-07-12, JAMUNDI, **HECHO** | 2 | 3 | +1 (alta H-3; la víctima ausente no resta hecho) |
| `HOMICIDIO`, mismo periodo/territorio, **HECHO** (propuesta) | 1 | 1 | 0 |
| `HOMICIDIO_VICTIMAS`, mismo periodo/territorio, **VICTIMA** | 3 | 2 | −1 (una fila menos en B) |
| `POLICIA_REGISTROS`, mismo periodo, **REGISTRO_ORIGEN** | 4 | 4 | 0 (diagnóstico, no oficial) |
| Distribución barrio X / Y / Z (HECHO) | X=1, Y=0, Z=0 | X=0, Y=1, Z=1 | Corrección mueve territorio sin crear hecho |
| Reclasificación HURTO→LESIONES (HECHO) | HURTO=1, LESIONES=0 | HURTO=1 (H-3), LESIONES=1 (H-2) | Total neto +1, composición cambia |

## Recorrido staging (DB → API → Dashboard → publicación → PDF → conciliación → chat, 2 usuarios/navegadores)

1. Restaurar copia controlada; aplicar `20260908_conciliacion_historica.sql`; correr `scripts/verify_staging_conciliacion.py` (0 fallos).
2. Cargar A (usuario 1, navegador 1) → anotar `source_version_id_A` (UUID IngestionRun COMPLETED).
3. `POST /api/sisc-cifras/indicator` × cada fila de la tabla con `source_version_id_A` → verificar valores A.
4. Publicar boletín con A (fija entrega): guardar `publication_id`, `query_hash`, PDF y `pdf_sha256`.
5. Dashboard: `OfficialQueryPanel` con entrega A → cifra oficial A; `currentYTDCount` del Excel debe etiquetarse **registros, no oficial**; publicación bloqueada sin cifra oficial o con error.
6. Cargar B (usuario 2, navegador 2) → `source_version_id_B`.
7. `POST /api/sisc-cifras/indicator` con B → verificar valores B; `POST /api/sisc-cifras/reconcile {publication_id, new_source_version_id: B}` → diferencia +1, nota con altas=1, reclasificaciones=1, ausentes=1 (víctima), metodología sin cambio.
8. Re-descargar `GET /api/sisc-cifras/publications/{publication_id}/pdf` (A): bytes idénticos (`sha256` igual) y cifras A intactas. Distinguir integridad de archivo vs igualdad estadística.
9. Chat `POST /api/ia/chat_ciudadano` mismos filtros/versiones → `provenance` coincide (indicador, unidad HECHO, periodo, entrega, metodología).
10. Repetir 3–9 desde segundo navegador/usuario: mismo historial central (`GET /api/central-history`), misma conciliación.
11. Importar un borrador local vía `POST /publications/import-legacy`: sin entrega recalculable → `CIFRAS_DECLARADAS` con razón; reimportar misma huella → `409`.

## Criterio de cierre

- Ningún conteo local alimenta cifras oficiales (Excel = previsualización etiquetada).
- Historial proviene del servidor; localStorage solo `sisc_official_prefs` y `sisc_legacy_imported_hashes`.
- Publicación A inmutable tras cargar B (contenido + PDF).
- Misma consulta + mismas versiones coincide en Dashboard, boletín y chat, con unidad/corte/versión visibles.
- Firma Observatorio en paralelo; hasta entonces HOMICIDIO=HECHO es **propuesta v1**.
