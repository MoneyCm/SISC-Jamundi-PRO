# Centro de fuentes

El Centro de fuentes consolida el control operativo de los origenes de datos del SISC. No consolida ni suma sus cifras: cada conector conserva su metodologia, cobertura y fecha de corte.

## Fuentes registradas

| Codigo | Fuente | Uso en SISC | Actualizacion |
| --- | --- | --- | --- |
| `POLICIA_JAMUNDI` | Sabana semanal de la Estacion de Policia | Fuente operativa principal | Carga institucional semanal |
| `POLICIA_NACIONAL` | Archivos publicos de Policia Nacional | Contraste de archivos publicos | Monitor automatico |
| `MINDEFENSA` | Estadistica del Ministerio de Defensa | Contraste institucional | Monitor automatico |
| `SIEDCO_PUBLICO` | Portal publico SIEDCO | Contraste estadistico | Monitor externo cada 12 horas |
| `OBSERVATORIO_VALLE` | Observatorio del Delito del Valle | Contexto territorial | Monitor externo diario |

## API

- `GET /api/source-center`: resumen institucional de conectores, cortes, calidad y activos.
- `POST /api/source-center/check/{connector_code}`: revisa MinDefensa o Policia Nacional. Acepta `dataset_code` como parametro opcional para revisar un solo archivo.
- `POST /api/source-center/heartbeat`: registra el resultado de un monitor externo.

El `heartbeat` puede autenticarse con un usuario operativo, con el encabezado
`X-SISC-SOURCE-KEY` o mediante un token OIDC de GitHub Actions. Los workflows
autorizados de `monitor-siedco` y `monitor-valle` usan OIDC con la audiencia
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

Los umbrales son mas estrictos para la sabana semanal de Policia Jamundi y mensuales para las fuentes nacionales y territoriales.
