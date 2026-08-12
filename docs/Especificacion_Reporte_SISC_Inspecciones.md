# Reporte agregado de Inspecciones para SISC

## Proposito

Esta plantilla permite integrar indicadores mensuales de las Inspecciones de Policia al SISC sin transferir expedientes, comparendos ni datos personales.

## Archivo de entrega

- Formato: CSV UTF-8 o Excel XLSX.
- Hoja obligatoria en Excel: `Reporte_SISC`.
- Frecuencia: mensual, dentro de los cinco primeros dias habiles del mes siguiente.
- Una fila representa un indicador agregado, no un caso individual.

## Columnas obligatorias

| Columna | Regla |
| --- | --- |
| `fecha_corte` | Ultimo dia incluido en el reporte, formato `AAAA-MM-DD`. |
| `anio` | Ano del periodo reportado. |
| `mes` | Mes del periodo reportado. |
| `dependencia` | Nombre de la Inspeccion responsable. |
| `indicador` | Nombre normalizado del indicador. |
| `categoria` | Desagregacion aprobada del indicador o `Total`. |
| `zona_general` | `Municipal`, `Urbano`, `Rural`, comuna o corregimiento permitido. |
| `valor` | Numero entero no negativo. Para recaudo, valor en pesos colombianos. |
| `fuente` | Reporte, sistema o matriz institucional de origen. |
| `observaciones` | Nota metodologica no sensible, si aplica. |

## Indicadores iniciales

- Procesos verbales abreviados.
- Citaciones y audiencias.
- Oficios y comunicaciones.
- Autos emitidos.
- Actas de conminacion.
- Tramites administrativos.
- Recaudo por tramites.
- Medidas correctivas gestionadas.
- Medidas correctivas pendientes.
- Medidas correctivas cerradas o pagadas.

## Reglas de privacidad

- No incluir nombres, documentos, telefonos, direcciones, expedientes, comparendos, relatos, pruebas ni datos de funcionarios.
- No incluir fecha u hora exacta del hecho.
- No publicar en el portal ciudadano categorias territoriales o poblacionales con menos de 10 registros.
- Las tablas de casos individuales permanecen en el sistema fuente y no se cargan al SISC ciudadano.

## Validaciones para SISC

- Rechazar archivos que incluyan columnas prohibidas o valores negativos.
- Conservar version, fecha de carga y responsable institucional.
- Mostrar primero el reporte como borrador para validacion del Observatorio.
- Publicar solo indicadores agregados aprobados.
