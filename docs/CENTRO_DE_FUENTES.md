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

La sabana semanal es la fuente operativa principal. Policia/SIEDCO se usan para
el contraste mensual oficial, Valle para el contexto regional y MinDefensa como
respaldo historico. Las cifras de fuentes distintas nunca se suman entre si.

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
autorizados de `monitor-mindefensa`, `monitor-policia`, `monitor-siedco` y
`monitor-valle` usan OIDC con la audiencia
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

## Lectura operativa

- **Al dia**: la fuente fue revisada y el corte esta dentro del umbral de vigencia.
- **Con rezago**: la fuente funciona, pero su corte supera el umbral esperado.
- **Desactualizada**: el corte supera el limite de rezago.
- **Nueva version**: el monitor detecto un archivo distinto al ultimo revisado.
- **Sin revisar**: existe conexion, pero falta corte o comprobacion.
- **Sin conexion**: el SISC aun no recibe estado de ese monitor.

Los umbrales son mas estrictos para la sabana semanal y Valle. Las fuentes
nacionales mensuales admiten el rezago normal entre el corte estadistico y la
fecha de publicacion institucional.
