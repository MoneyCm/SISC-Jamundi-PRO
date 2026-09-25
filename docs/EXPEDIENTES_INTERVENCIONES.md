# Expedientes de decisiones e intervenciones

Implementado y verificado en staging el 8 de septiembre de 2026.

## Uso

En la plataforma, abrir `/alertas`, autenticar la sesión institucional y seleccionar
una alerta. La sección **Decisiones e intervenciones** permite consultar expedientes
asociados o crear uno con problema y valoración del analista.

1. **BORRADOR:** problema y valoración obligatorios.
2. **DECIDIDA:** recomendación, decisión/referencia de acta, responsable, fecha y plazo.
3. **EN_EJECUCION:** descripción de la intervención e inicio real.
4. **FINALIZADA:** finalización real y al menos una referencia documental HTTP(S).
5. **EVALUADA:** comparación calculada en el servidor e interpretación del analista.

Cada guardado conserva una revisión con usuario autenticado, fecha del servidor y
documento completo. El control de versión devuelve 409 si otro analista guardó primero;
usar **Recargar expediente** y revisar el historial antes de volver a editar.
Un expediente evaluado se conserva sin edición. No existen endpoints de borrado.
Las referencias documentales son enlaces y descripciones: no se descargan ni se verifica
automáticamente la autenticidad del documento enlazado.

## Comparación

Se usa exclusivamente `calculate_indicator`, con la misma entrega y metodología para
ambos períodos. Los extremos son inclusivos; deben tener igual duración, no solaparse,
y quedar antes del inicio y después del fin de la intervención, respectivamente.
La entrega policial debe estar COMPLETED y declarar cobertura para todo el intervalo.
La versión metodológica debe ser ejecutable. No se aceptan cifras manuales.

Alcance inicial: HOMICIDIO y SEGURIDAD_TOTAL, territorio JAMUNDI, heredados de la alerta.
No se presentan resultados municipales como evaluación de un barrio. La definición
institucional de homicidio por hechos continúa pendiente del Observatorio.

Se conservan ambos resultados con procedencia, diferencia absoluta, variación porcentual
(null cuando la base es cero), interpretación y nota de no causalidad.
El resultado inicial representa el período anterior recalculado con la entrega fijada
para la evaluación; no se presenta como una cifra publicada originalmente.
Igual duración no controla estacionalidad ni otros factores: la interpretación es humana.

## API y datos

- GET `/api/interventions/?alert_id=UUID`: expedientes vinculados; acceso institucional.
- POST `/api/interventions/`: crear borrador; analista/admin.
- GET `/api/interventions/{id}`: documento y todas sus revisiones.
- PUT `/api/interventions/{id}`: documento completo y `expected_version`.
- POST `/api/interventions/{id}/evaluate`: períodos, entrega, metodología,
  interpretación y `expected_version`.

Tablas: `intervention_cases`, `intervention_revisions`; FK a alerta y expediente;
unicidad de revisión por expediente/versión. La evidencia de la alerta se copia al crear
el expediente y no se modifica al cambiar una decisión ni al reevaluarse la alerta.
Bloqueo de fila en PostgreSQL junto con versión esperada para evitar escrituras perdidas.

Migración aditiva: `backend/db/migrations/20260908_interventions.sql`.
Aplicada a `sisc_staging` local. No aplicada a producción en esta intervención.

## Verificación reproducible

Desde `backend`:

```powershell
python scripts/verify_interventions_staging.py --uri-file RUTA_URI_LOCAL --regression
```

El script restringe el destino a localhost y `sisc_staging`, no imprime credenciales,
aplica la migración aditiva y ejecuta la selección de regresión. El recorrido de prueba
de PostgreSQL revierte sus datos al terminar.

Resultado observado: **178 passed**, sin pruebas omitidas en esa selección.
TypeScript: `tsc --noEmit`, código 0. No se afirma que la suite completa del repositorio
haya sido ejecutada.

Prueba PostgreSQL: cinco revisiones, rechazo de versión obsoleta, evidencia de alerta
preservada, cálculo real 2→1 (-50 %), expediente evaluado no editable y lectura compartida.
Pruebas de validación: fechas, campos, evidencias, cobertura, períodos iguales,
base cero y restricción de escritura institucional.

## Recorrido visual observado

Navegador de la aplicación, Next `127.0.0.1:3100` → backend de staging `127.0.0.1:8001`.
Backend de staging reiniciado para cargar el nuevo router; sin cambiar `.env.local`.

- Alerta: `f61d13fe-6b22-4058-b614-7735cc8b46a4`.
- Expediente sintético: `8fbd4326-be26-4a3d-afd2-2ee5d7839dd6`.
- Actor de pruebas: `visual_analyst`.
- Flujo visible BORRADOR v0 → DECIDIDA v1 → EN_EJECUCION v2 → FINALIZADA v3 → EVALUADA v4.
- Intento de finalizar sin evidencia rechazado con mensaje visible.
- Antes 24–28 junio: 0 hechos; después 1–5 julio: 1 hecho. Misma entrega
  `5e7ceba9-ba0a-4850-9e17-53e7465c4f62`, metodología 1.
- Diferencia +1, porcentaje no calculable por base cero y nota explícita de no causalidad.
- Después de recargar la aplicación, el expediente conserva cifras, estado y cinco revisiones.
- Captura inspeccionada en el navegador: resultado legible en viewport estrecho,
  estado EVALUADA y sin botón de guardado sobre el expediente cerrado.

Evidencia estructurada sin tokens: [interventions_staging.json](evidence/interventions_staging.json).
SHA-256: `e7b28c1a1f8c39f2c79be0d9097d425d02ca3601294321be03f1c49307c4a670`.
El expediente visual se conserva como datos de prueba explícitamente identificados.

Los límites previos (PostGIS real, LLM del chat y definición institucional de homicidio)
permanecen separados de esta aceptación.
