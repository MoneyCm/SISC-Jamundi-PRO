# Acta de aceptación staging — conciliación histórica (intervención única)

Fecha ejecución live: 2026-09-08 ~13:40 (America/Bogota).
Metodología HOMICIDIO=HECHO: **propuesta v1, pendiente Observatorio** (separada del resultado técnico).

## Entorno (aislado de producción)

- PostgreSQL embebido `pgserver` (proceso `stage_pg.py`), base `sisc_staging` creada para la prueba.
- PostGIS ausente en el build embebido → stubs SQL `st_point/st_setsrid/st_geomfromtext`
  (la columna `location_geom` es `Text` y ajena a las cifras; documentado en el runbook).
- Backend FastAPI live `127.0.0.1:8001` con `DATABASE_URL` a `sisc_staging` (`stage_api.py`).
- Frontend Next dev (puerto 3100) con `SISC_API_URL=http://127.0.0.1:8001/api` (override en shell;
  `.env.local` apunta a producción y no se usó).
- Geocodificación remota sin red → fallback a coordenadas por defecto (registrado en logs, no afecta cifras).

## Versiones

- SISC-Jamundi-PRO + esta intervención (incluye 2 correcciones halladas por staging:
  `setdefault` que dejaba `source_version_id=None`, y `record_key` por identidad que
  colapsaba multivíctimas → ahora `identidad#huella`, correspondencia por identidad).
- plataforma-seguridad + `OfficialQueryPanel`, `CentralHistoryPanel`, `useOfficialIndicator`,
  proxies `official-indicator/central-reconcile/central-history`,
  `officialMatchesCurrentQuery` compara entrega seleccionada (no solo existente) y
  restringe explícitamente a JAMUNDI + SEGURIDAD_TOTAL.
- Migración `20260908_conciliacion_historica.sql` aplicada sin errores sobre esquema real.

## Identificadores observados

- Entrega A: `d5c49bc5-0109-41db-9ccd-2afce07921d5` (usuario staging_user_1, 4 filas, 0 rechazadas)
- Entrega B: `b2bb9139-51ef-4573-8ab9-0b3fbbea9aaf` (usuario staging_user_2)
- Publicación A: `c468d460-f30f-409a-a925-1f601ec52113` (weekly 2026-07-01–05, PUBLISHED, met v1)
- PDF A: 3090777 bytes, `sha256=3d0a41824f61e29f…566b9`
- `qh(SEG_TOTAL,A)=ad9f0e0e975b…` idéntico en proceso, HTTP directo y proxy Next.
- `qh(HOMICIDIO,B)=9fa87e0c56a8…` idéntico en HTTP directo y proxy.

## Resultados por paso (32/32 OK en `stage_accept.json`)

| Paso | Evidencia |
|---|---|
| 1 migración/verificador | esquema + migración OK, base fresca, columnas `content_hash/identity_confidence` presentes |
| 2 A → 2, 1, 3, 4 | `SEG_TOTAL=2 HECHO, HOMICIDIO=1 HECHO, VICTIMAS=3, REGISTROS=4`, qh registrados |
| 3 publicar A + PDF | `source_version_ids.POLICIA_SEMANAL=runA`, met 1, approve PUBLISHED, PDF+sha guardados |
| 4 B → 3, 1, 2, 4 | mismos 4 indicadores con unidades explícitas |
| 5 conciliar A→B | dif +1 (2→3); altas=1 (H-3), reclasif=1 (H-2), modif=1 (H-1 con 1 víctima menos), ausentes=0; nota ausente≠eliminado presente |
| 6 Dashboard/boletín/chat | misma vía (`calculate_indicator`); chat HTTP 200 (LLM sin clave → mensaje fallback; capa de datos verificada) |
| 7 reabrir A | PDF bytes idénticos (`sha` igual), status PUBLISHED intacto |
| 8 2º usuario | mismo historial central (1 publicada) |
| N1 sin entrega | 422 "exige entrega fija" |
| N2 met vieja | 422 "no ejecutable" |
| N3 cifra local 999 | 422 "no coincide con el servidor" |
| Import | `REPRODUCIBLE` (2==2 recalculado); duplicado → 409 |
| HTTP directo | `/indicator` A=2, B/HOMICIDIO=1, met=0 → 422 |
| Proxy Next | `/central-history` → pub A; `/official-indicator` → HOMICIDIO=1 mismo qh |

## Criterio de cierre

Aceptación técnica: **CERRADA** con evidencia. Pendientes fuera de esta intervención:
firmas del Observatorio (unidad de homicidio) y motor de alertas (ventanas/cobertura/ceros).

## Anexo 2026-09-08 p.m. — alerta semanal reproducible (HOMICIDIO)

(Contenido original de este anexo sin cambios; sigue debajo.)

## Anexo 2026-09-08 noche — DashboardV2 migrado + cierre visual de bandeja

- Build probado: `npm run build` (Vite OK, `DashboardV2-DptSbXcF.js`) + render live en
  `:5173` contra backend espejo `:8000` (staging). Destino staging en ambas interfaces
  (`:3100`→`:8001`, `:5173`→`:8000`, misma base `sisc_staging`).
- Alerta utilizada en el visual: `f61d13fe-6b22-4058-b614-7735cc8b46a4` (entrega F,
  OPEN PENDIENTE v0, 0 revisiones, linaje con `2c2418e8…` como previa).
- Transiciones observadas en vivo: PENDIENTE → EN_ANALISIS (v1, comentario+autor) →
  descarte vacío bloqueado → DESCARTADA con motivo (v2); relectura con historial intacto.
- Evidencias: `Temp/opencode/shots/shot-01-detail.png`, `shot-02-error.png`,
  `shot-03-discarded.png`, `shot-04-history.png`, `shot-05-dashboardv2.png`,
  `shot-06-widget.png`; `stage_accept.json` (32/32); `visual_token.txt` (solo staging).
- DashboardV2 consume bandeja (`/alerts-tray`, solo OPEN; vista previa SIN_ALERTA/
  SIN_COBERTURA/ERROR diferenciadas): verificado en vivo con la misma alerta —
  tarjeta P2 "0 → 1 HECHO", "Revisión DESCARTADA", coherente con la bandeja
  (ninguna alerta anterior aparece vigente; revisiones consultables).
  Nota: un assert inicial leyó el estado de carga vacío ("Sin alertas vigentes");
  se corrigió esperando `Actualizado:` (carga completa) antes de afirmar.
- Formulación de validación: **175 pruebas del alcance pasan; suite completa no
  validada por dependencia de PostgreSQL**.
- Pendientes separados (no bloquean la bandeja): homicidio institucional,
  PostGIS real, LLM del chat. Siguiente módulo: expediente de decisiones e
  intervenciones vinculado a la alerta.

Estado: **visual verificado** (cronología consultada antes: sin escrituras parciales;
alerta controlada `f61d13fe…` creada para este recorrido: OPEN PENDIENTE v0, 0 revisiones).

- Proxy corregido según Next 16.2.9 (`await context.params` en `[id]` y `[id]/review`);
  lista y detalle 200 con el id reenviado coincidiendo con el solicitado.
  Destino confirmado: Next 3100 → backend staging `:8001` (intento en 3121 descartado:
  lock dev ajeno + Turbopack rechaza junctions; copia temporal eliminada).
- Interfaz: token en ref sincrónica + Recargar deshabilitado sin token; hidratación
  esperada vía carga inicial. Un solo intento por paso (sin reintentos que oculten fallos).
- Recorrido: abrir (evidencia, cronología vacía, linaje 4) → EN_ANALISIS explícito
  (v1, comentario+autor visibles) → descarte vacío bloqueado ("Descartar exige motivo",
  verificado en DOM) → descarte con motivo (DESCARTADA v2) → relectura de historial
  (2 revisiones con autor, fecha y comentario; linaje intacto).
- Capturas revisadas una por una: `shots/shot-01-detail.png`, `shot-02-error.png`,
  `shot-03-discarded.png`, `shot-04-history.png` (formato de evidencia pulido tras verlas:
  períodos y regla legibles en vez de JSON crudo).

## Anexo previo — bandeja operativa (dos analistas + retrospectiva, resumido)

- Arranque normal importa todos los modelos en `create_tables()` (`db/models.py:9-20`):
  el incidente del espejo legacy fue artefacto de un script sin imports.
  Prueba `test_arranque_importa_todos_los_modelos` bloquea FK huérfanas.
  Falla parcial visible en `stats`/issues y recuperable por reintento idempotente (misma entrega C completó 6/6).
- Migración `20260908_bandeja_alertas.sql` aplicada (7 statements, con backfill de
  `lineage_key` para evaluaciones previas).
- Dos analistas live: `EN_ANALISIS`(a1) → historial compartido → `REVISADA`(a1) →
  stale de a2 **409**, descarte sin motivo **422**, `DESCARTADA`(a2, v4) con autoría.
- Retrospectiva D (sin homicidio, cobertura completa 06-22–07-05): `SIN_ALERTA` +
  `lineage.superseded=[371f78ee…, 68ecc5ff…]` con "Ya no cumple la regla";
  revisiones y `DESCARTADA` anteriores conservadas, nueva evaluación nace `PENDIENTE`
  (sin herencia). Vigente = última del linaje.
- Endpoints HTTP live (`TestClient` + backend reiniciado): lista 200 (2 ítems),
  detalle 200 (4 revisiones, linaje 2, transiciones), review 409/422, ciudadano 403.
  Proxy Next `/api/tray` → 401 sin token (auth extremo a extremo); `/api/official-indicator`
  → `SEG_TOTAL=3` con entrega B (misma cifra que el servicio).
- UI: página `/alertas` (`AlertsTray`) con lista, evidencia, regla, versiones, cronología,
  linaje y revisión con `expected_version`; `tsc` EXIT 0. `DashboardV2` (SISC frontend)
  ya consulta `/alerts-tray/` y usa `/ia/alertas-semanales` para previsualizar cobertura
  cuando no hay evaluaciones persistidas (verificado en código el 08/09/2026).
  La migración del widget ya no es un pendiente.
- Batería alcance: **173 passed**. `test_inspecciones.py` falla por requerir Postgres en
  `:5432` (preexistente, ajeno a esta intervención).

- Regla APARICION explícita: P2 desde 1 caso, sin porcentaje, con justificación en
  código (`WEEKLY_THRESHOLDS.HOMICIDIO.aparicion`), pruebas y evidencia (`applied_rule`).
- Cobertura desde la entrega declarada (`cobertura_inicio/fin`): entrega B (07-02–07-05)
  → `SIN_COBERTURA/DESCONOCIDA` para ventanas 22/6–5/7 (live). Entrega C (06-22–07-05)
  → `ALERTA P2 APARICION_DE_CASOS`, cur=1 prev=0, `COMPLETA`, `applied_rule` explícita.
- Dedupe `WEEKLY:indicador:territorio:semana:entrega:metodología:RULES_VERSION=R1`,
  persistida `68ecc5ff…`, re-emisión `duplicate:true`; la fila con clave vieja convive
  como historial (las reglas nuevas no reutilizan resultados viejos).
- `GET /alertas-semanales` consulta sin persistir; `POST /alertas-semanales` ejecuta
  (requiere rol analista). Batería 145+13 passed.

## Límites explícitos del alcance probado
Actualización 08/09/2026: el nuevo expediente de decisiones e intervenciones fue
implementado, migrado a PostgreSQL staging y probado desde la interfaz. Ver
[acta del módulo y evidencia](EXPEDIENTES_INTERVENCIONES.md). Selección de regresión
ejecutada: **178 passed**, incluido recorrido PostgreSQL real; TypeScript sin errores.
El cierre corresponde al alcance municipal descrito, no a despliegue en producción.

- **Geografía no validada**: los stubs PostGIS (`st_point/st_setsrid`) no equivalen a probar
  operaciones espaciales. Ninguna cifra oficial depende de ellos (`location_geom` es `Text`),
  pero focos territoriales/hotspots con PostGIS real quedan fuera de esta aceptación.
- **Chat parcialmente validado**: se verificó transporte HTTP (200), mensaje fallback sin clave
  y capa de datos (mismo servicio, `provenance` con unidad/período/entrega/metodología).
  Queda pendiente la respuesta del proveedor LLM con su configuración real.
- La definición institucional HOMICIDIO=HECHO sigue pendiente del Observatorio: no invalida
  las pruebas técnicas, pero condiciona su uso como indicador oficial.

## Anexo — revisión de cambios Codex (interventions + generator)

- Backend importa OK con el router `/api/interventions` (`/`, `/{case_id}`, `/{case_id}/evaluate`;
  sin colisiones con `/api/alerts-tray`). El módulo usa `calculate_indicator`, nota explícita
  de no-causalidad y estados con validación; no duplica la bandeja.
- `GenerateSiscCifrasRequest.source_version_id` + `_check_selected_delivery` reutilizan
  `require_fixed_delivery` y exigen que la entrega fijada sea la vigente (409 si cambia).
- Batería: **198 passed, 1 skipped** (175 del alcance + 23 de Codex). `tsc` EXIT 0.
- `OfficialQueryPanel` reescrito por Codex (entrega por prop desde `SabanaUploadFlow`,
  auto-consulta SEGURIDAD_TOTAL; hook con stale-guard intacto). La aceptación visual
  previa (shots 01–04, panel manual) **no cubre este flujo nuevo**: requiere repaso visual
  (login por sesión + upload + consulta automática + publicación fijada).
- Pendiente de Codex: borrar `.codex-temp-comisaria*/`.
