# SISC Jamundí - Sistema de Información para la Seguridad y la Convivencia

## 1. Indicadores del MVP

### A. Tasa de Homicidios (año/proyectada)
- **Fórmula**: (Nº Homicidios / Población Total) * 100,000.
- **Población Jamundí (Estimada)**: 150,000 habitantes.
- **Frecuencia**: Mensual.

### B. Variación Porcentual
- **Fórmula**: ((Hechos Mes Actual - Hechos Mes Anterior) / Hechos Mes Anterior) * 100.
- **Frecuencia**: Semanal / Mensual.

### C. Densidad Espacial (Hotspots)
- **Método**: Kernel Density Estimation (KDE) o conteo por grilla hexagonal/territorio.
- **Visualización**: Mapa de calor por barrios.

### D. Distribución Temporal
- **Análisis**: Día de la semana, Franja horaria (Mañana, Tarde, Noche, Madrugada).

## 2. Productos (Salidas)

### Boletín de Seguridad Mensual (PDF)
- **Contenido**:
    - Resumen ejecutivo.
    - Tabla comparativa vs año anterior.
    - Gráfico de barras por tipo de delito.
    - Mapa de delitos críticos.
    - Top 5 barrios con mayor incidencia.

### Reporte de Alertas Tempranas
- **Lógica**: Disparo de alerta si un delito aumenta más del 20% en una zona específica respecto al promedio del trimestre anterior.

### Dataset Público (Portal de Transparencia)
- **Formato**: CSV / JSON.
- **Nivel de agregación**: Mes / Categoría / Barrio.
- **Privacidad**: Sin coordenadas exactas (solo centroide de barrio) y sin microdatos de víctimas.
