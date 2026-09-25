# Centro de fuentes

El Centro de fuentes consolida el control operativo de los origenes de datos del SISC. No consolida ni suma sus cifras: cada conector conserva su metodologia, cobertura y fecha de corte.

## Fuentes registradas

| Codigo | Fuente | Uso en SISC | Actualizacion |
| --- | --- | --- | --- |
| `POLICIA_JAMUNDI` | Sabana semanal de la Estacion de Policia | Fuente operativa principal | Carga institucional semanal |
| `POLICIA_NACIONAL` | Registros oficiales de Policia Nacional | Contraste mensual oficial | Revision diaria 07:29; procesa solo cambios |
| `MINDEFENSA` | Estadistica del Ministerio de Defensa | Respaldo historico de Policia | Revision diaria 07:17; procesa solo cambios |
| `SIEDCO_PUBLICO` | Portal publico SIEDCO | Validacion mensual | Dia 18 a las 07:53 o ejecucion manual |
| `OBSERVATORIO_VALLE` | Observatorio del Delito del Valle | Contexto regional para el cierre mensual | Lunes a las 07:41 |
| `FISCALIA_SPOA_V3` | Fiscalía General de la Nación, SPOA V3 | Capa judicial complementaria | Lunes a viernes a las 07:17; publicación mensual |
| `MEDICINA_LEGAL` | Instituto Nacional de Medicina Legal y Ciencias Forenses | Capa forense que arbitra lesiones de causa externa | Preliminar mensual mes vencido; definitivas anuales |

La sabana semanal es la fuente operativa principal. Policia/SIEDCO se usan para
el contraste mensual oficial, Valle para el contexto regional y MinDefensa como
respaldo historico. Fiscalía SPOA aporta contexto judicial de procesos, víctimas
y procesados. Medicina Legal aporta la clasificación forense —que no tipifica
delito y se entrega en presunción— para arbitrar homicidios, suicidios y
violencia de causa externa contra SIEDCO y SPOA. Las cifras de fuentes
distintas nunca se suman entre si.

## Referencia territorial y nacional

El monitor de MinDefensa conserva su flujo local de Jamundi para el boletin y
las notificaciones. La carga de referencia es un proceso separado y manual:
desde GitHub Actions se ejecuta con `force_download=true` y
`sync_reference=true`. Esta carga envia al SISC solo agregados por conducta,
municipio, ano y mes con codigo DANE y fecha de corte; no envia barrios ni datos
personales. El comparador regional o nacional solo se activa cuando cada
conducta tiene cobertura municipal completa y un corte unico verificable.

Los monitores diarios consultan primero los metadatos remotos disponibles
(fecha, tamano, ETag o huella). Solo descargan, procesan y notifican cuando el
estado remoto cambia. La sabana
semanal se procesa dentro del SISC o en almacenamiento privado y no se publica
como artefacto de GitHub Actions.

Las ejecuciones manuales tampoco notifican por defecto. El operador puede
forzar el procesamiento o el correo mediante los controles explicitos del
workflow, sin confundir una prueba tecnica con una nueva publicacion.

## API

- `GET /api/source-center`: resumen institucional de conectores, cortes, calidad y activos.
- `POST /api/source-center/check/{connector_code}`: conservado por compatibilidad; las fuentes externas se revisan en sus workflows y responden `409` para evitar procesos duplicados.
- `POST /api/source-center/heartbeat`: registra el resultado de un monitor externo.

El `heartbeat` puede autenticarse con un usuario operativo, con el encabezado
`X-SISC-SOURCE-KEY` o mediante un token OIDC de GitHub Actions. Los workflows
autorizados de `monitor-mindefensa`, `monitor-policia`, `monitor-siedco`,
`monitor-valle` y `monitor-fiscalia-spoa-v3` usan OIDC con la audiencia
`sisc-source-center`; el backend valida firma, repositorio, archivo de workflow,
rama, evento y entorno de ejecucion. No requieren secretos permanentes.

`SISC_SOURCE_MONITOR_KEY` permanece disponible para monitores que se ejecuten
fuera de GitHub Actions. Esa clave nunca debe viajar en la URL ni quedar escrita
en un repositorio.

```json
{
  "connector_code": "SIEDCO_PUBLICO",
  "status": "CURRENT",
  "quality_status": "VALIDATED",
  "period_label": "Corte al 2026-08-10",
  "source_cutoff_date": "2026-08-10",
  "last_checked_at": "2026-08-12T12:00:00Z",
  "last_success_at": "2026-08-12T12:00:00Z",
  "record_count": 0,
  "indicator_count": 11,
  "warnings": [],
  "details": {
    "workflow": "monitor-siedco"
  }
}
```

Estados de monitor permitidos: `CURRENT`, `UPDATED`, `UPDATE_AVAILABLE`, `ERROR` y `NEEDS_REVIEW`.

Estados de calidad permitidos: `VALIDATED`, `WARNING`, `INCOMPLETE` y `ERROR`.

### Ingesta Fiscalía SPOA V3

- `POST /api/fiscalia-spoa/ingest`: recibe lotes de hasta 1.000 filas anonimizadas y validadas.
- `POST /api/fiscalia-spoa/runs/{run_id}/complete`: cierra la ejecución y registra boletín/hash.
- `GET /api/fiscalia-spoa/summary`: resumen de cortes y conteos únicos para usuarios institucionales.

La ingesta admite exclusivamente los identificadores Socrata oficiales y se
autentica con el mismo OIDC/clave del Centro de fuentes. Los snapshots son
idempotentes por conjunto, corte y SHA-256; las filas por snapshot también
tienen una clave única. Los identificadores anonimizados permanecen opacos.

### Ingesta Medicina Legal

- `GET /api/medicina-legal/summary`: cortes, versiones y conteos por dataset para usuarios institucionales.

`python backend/ingest_medicina_legal.py` descarga de datos.gov.co (SODA) los
conjuntos del INMLCF, conserva Valle del Cauca y guarda los registros de
Jamundí (`codigo_dane_municipio=76364`):

| Dataset SISC | Dataset datos.gov.co | Naturaleza |
| --- | --- | --- |
| `HOMICIDIOS_DEF` | Presuntos homicidios 2015-2024 (`vtub-3de2`) | Definitivas |
| `SUICIDIOS_DEF` | Presuntos suicidios 2015-2024 (`f75u-mirk`) | Definitivas |
| `FATALES_PRE` | Lesiones fatales preliminar (`2kpj-cktv`) | Preliminar mensual |
| `NOFATALES_PRE` | Lesiones no fatales preliminar (`79dd-d24f`) | Preliminar mensual |

Los snapshots son idempotentes por conjunto, corte y SHA-256 del lote, con la
misma garantía anti-sobrescritura que SPOA. El corte se fija al último periodo
presente (mes vencido) y queda marcado `definitive` según corresponda. La
clasificación es forense y en presunción: no tipifica delito, y se usa como
árbitro en la reconciliación, nunca como fuente que se suma.

## Lectura operativa

### Sincronizacion de la instalacion local

Los workflows reportan a Render, no a `localhost`. Para recibir sus reportes en
la base local, ejecutar `python backend/scripts/sync_source_monitors.py` en el
equipo con GitHub CLI autenticado (`gh auth login`). `--watch` repite la consulta
cada 15 minutos; `START_SISC_AUTO.bat` inicia este proceso oculto sin duplicarlo.
La sincronizacion no ejecuta monitores, no envia correos y rechaza bases remotas.

Los cinco monitores conservan `sisc-heartbeat.json` en el artefacto
`sisc-heartbeat` durante 30 dias, incluso si falla el envio a Render. El lector
solo acepta el workflow registrado de `main`, ejecuciones programadas o manuales
y el conector esperado. Conserva las fechas reales del reporte, valida el JSON
y no reemplaza reportes recientes por antiguos.

Las ejecuciones anteriores que no tengan este artefacto solo acreditan que el
monitor existe y se ejecuto: se registran como **Sin revisar**, con advertencias
y enlace de procedencia, sin inventar fecha de revision, corte ni cifras. Esta
evidencia parcial nunca sustituye un reporte real ya recibido. Los cambios de
los workflows deben publicarse para que las proximas ejecuciones guarden el
artefacto. Los emisores reintentan tres veces los fallos temporales; un 404 no
se reintenta y requiere revisar la version/ruta desplegada en Render.

- **Al dia**: la fuente fue revisada y el corte esta dentro del umbral de vigencia.
- **Con rezago**: la fuente funciona, pero su corte supera el umbral esperado.
- **Desactualizada**: el corte supera el limite de rezago.
- **Nueva version**: el monitor detecto un archivo distinto al ultimo revisado.
- **Sin revisar**: existe conexion, pero falta corte o comprobacion.
- **Sin conexion**: el SISC aun no recibe estado de ese monitor.

Los umbrales son mas estrictos para la sabana semanal y Valle. Las fuentes
nacionales mensuales admiten el rezago normal entre el corte estadistico y la
fecha de publicacion institucional.
