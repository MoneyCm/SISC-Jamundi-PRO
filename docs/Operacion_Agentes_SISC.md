# Operacion de agentes del SISC

## Objetivo

Convertir informes institucionales en indicadores trazables sin publicar datos sin aprobacion humana.

## Flujo

1. Recepcion: registra nombre y huella SHA-256 del archivo.
2. Extraccion: procesa CSV/XLSX y reconoce indicadores conocidos en PPTX/DOCX.
3. Calidad: marca valores extraidos de documentos narrativos para revision manual.
4. Privacidad: detecta posibles correos, telefonos y documentos de identidad.
5. Revision: un funcionario resuelve cada hallazgo y documenta la decision.
6. Aprobacion: sustituye versiones del mismo periodo sin borrar historial.
7. Publicacion: expone solo indicadores aprobados y sobre el umbral de privacidad.

## Reglas

- El agente nunca aprueba ni publica por si solo.
- El informe original se conserva en el repositorio institucional restringido.
- Se registra responsable, fecha de corte y version.
- Los PDF requieren la plantilla institucional para evitar OCR no confiable.