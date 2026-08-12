from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from db.models import Event, EventType
from db.models_hechos_seguridad import HechoSeguridad
from services.hechos_metrics import hechos_unicos_expr
import logging

logger = logging.getLogger("alert_engine")

NON_PUBLIC_TERRITORY_VALUES = {
    "BARRIO PENDIENTE POR ASIGNAR",
    "PENDIENTE POR ASIGNAR",
    "SIN ASIGNAR",
    "SIN BARRIO",
    "SIN COMUNA",
    "SIN ESPECIFICAR",
    "SIN LOCALIDAD",
    "NO APLICA",
    "NO APLICA LOCALIDAD",
    "NO APLICA LOCALIDAD - COMUNA",
    "NO DEFINIDO",
    "NO REPORTA",
    "NO REGISTRA",
    "N/A",
}
NON_PUBLIC_TERRITORY_PATTERNS = (
    "PENDIENTE",
    "POR ASIGNAR",
    "NO APLICA",
    "NO DEFINIDO",
    "SIN LOCALIDAD",
    "SIN COMUNA",
)


def is_public_territory_name(value):
    if not value:
        return False
    clean = " ".join(str(value).strip().upper().split())
    if not clean or clean in NON_PUBLIC_TERRITORY_VALUES:
        return False
    return not any(pattern in clean for pattern in NON_PUBLIC_TERRITORY_PATTERNS)


class AlertEngine:
    @staticmethod
    def get_unified_counts(db: Session, start_date, end_date, category=None):
        """
        Obtiene conteos deduplicados por día y categoría entre dos fechas.
        """
        # 1. Counts from Legacy Table
        query_leg = db.query(
            Event.occurrence_date.label('date'),
            EventType.category.label('cat'),
            func.count(Event.id).label('count')
        ).join(EventType).filter(Event.occurrence_date >= start_date, Event.occurrence_date <= end_date)

        if category:
            query_leg = query_leg.filter(EventType.category == category)

        leg_data = query_leg.group_by(Event.occurrence_date, EventType.category).all()

        # 2. Counts from Modern Table
        query_mod = db.query(
            HechoSeguridad.fecha_evento.label('date'),
            HechoSeguridad.categoria_delito.label('cat'),
            hechos_unicos_expr().label('count')
        ).filter(HechoSeguridad.fecha_evento >= start_date, HechoSeguridad.fecha_evento <= end_date)

        if category:
            query_mod = query_mod.filter(HechoSeguridad.categoria_delito == category)

        mod_data = query_mod.group_by(HechoSeguridad.fecha_evento, HechoSeguridad.categoria_delito).all()

        # 3. La SABANA es autoritativa cuando cubre el mismo día y categoría.
        merged = {}
        for d, c, count in leg_data:
            key = (d, c)
            merged[key] = count

        for d, c, count in mod_data:
            key = (d, c)
            # Sustituye el conteo legacy para evitar conservar filas por víctima.
            merged[key] = count

        # 4. Group by Category
        cat_totals = {}
        for (d, c), count in merged.items():
            cat_totals[c] = cat_totals.get(c, 0) + count

        return cat_totals

    @staticmethod
    def calculate_alerts(db: Session):
        """
        Analiza tendencias y genera alertas P1, P2 o P3.
        """
        hoy = datetime.now().date()
        hace_7 = hoy - timedelta(days=7)
        hace_14 = hoy - timedelta(days=14)
        hace_30 = hoy - timedelta(days=30)
        hace_60 = hoy - timedelta(days=60)

        # 1. Estadísticas de Corto Plazo (Semanal)
        actual_7 = AlertEngine.get_unified_counts(db, hace_7, hoy)
        prev_7 = AlertEngine.get_unified_counts(db, hace_14, hace_7 - timedelta(days=1))

        # 2. Estadísticas de Mediano Plazo (Mensual)
        actual_30 = AlertEngine.get_unified_counts(db, hace_30, hoy)
        prev_30 = AlertEngine.get_unified_counts(db, hace_60, hace_30 - timedelta(days=1))

        alertas = []

        # Categorías críticas de la Secretaría de Seguridad
        critical_cats = ['HOMICIDIO', 'HURTO', 'VIF', 'LESIONES', 'EXTORSION', 'SECUESTRO']

        for cat in critical_cats:
            # --- Alerta Semanal (Brotes Rápidos) ---
            act = actual_7.get(cat, 0)
            pre = prev_7.get(cat, 0)

            if act > 0:
                inc_pct = ((act - pre) / pre * 100) if pre > 0 else 100

                if inc_pct >= 25 or (cat == 'HOMICIDIO' and act >= 2):
                    tier = "P1" if inc_pct > 50 or (cat == 'HOMICIDIO' and act >= 3) else "P2"
                    alertas.append({
                        "id": f"W-{cat}-{hoy}",
                        "titulo": f"Incremento Semanal: {cat}",
                        "nivel": tier,
                        "categoria": cat,
                        "variacion": f"{round(inc_pct)}%",
                        "mensaje": f"Se detectó un aumento atípico en {cat} durante los últimos 7 días ({act} casos vs {pre} previos).",
                        "tipo": "TENDENCIA_SEMANAL",
                        "valor_actual": act,
                        "valor_previo": pre
                    })

            # --- Alerta Mensual (Sostenida) ---
            act_m = actual_30.get(cat, 0)
            pre_m = prev_30.get(cat, 0)

            if act_m > 0 and cat not in [a['categoria'] for a in alertas if a['nivel'] == 'P1']:
                inc_m_pct = ((act_m - pre_m) / pre_m * 100) if pre_m > 0 else 0
                if inc_m_pct > 15:
                    alertas.append({
                        "id": f"M-{cat}-{hoy}",
                        "titulo": f"Tendencia Mensual: {cat}",
                        "nivel": "P2" if inc_m_pct > 30 else "P3",
                        "categoria": cat,
                        "variacion": f"{round(inc_m_pct)}%",
                        "mensaje": f"La incidencia mensual de {cat} muestra un crecimiento sostenido del {round(inc_m_pct)}%.",
                        "tipo": "TENDENCIA_MENSUAL",
                        "valor_actual": act_m,
                        "valor_previo": pre_m
                    })

        # --- Alertas Territoriales (Barrios Críticos) ---
        # Solo para el año actual
        top_barrios = db.query(
            HechoSeguridad.barrio_normalizado,
            hechos_unicos_expr().label('total')
        ).filter(
            HechoSeguridad.fecha_evento >= hace_30,
            HechoSeguridad.barrio_normalizado.isnot(None),
            HechoSeguridad.barrio_normalizado != "",
            func.upper(func.trim(HechoSeguridad.barrio_normalizado)).notin_(NON_PUBLIC_TERRITORY_VALUES),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%PENDIENTE%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%POR ASIGNAR%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO APLICA%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO DEFINIDO%"),
        ).group_by(HechoSeguridad.barrio_normalizado).order_by(hechos_unicos_expr().desc()).limit(3).all()

        for b_name, b_count in top_barrios:
            if is_public_territory_name(b_name) and b_count >= 10:
                alertas.append({
                    "id": f"GEO-{b_name}-{hoy}",
                    "titulo": f"Foco de Inseguridad: {b_name}",
                    "nivel": "P2",
                    "categoria": "TERRITORIAL",
                    "variacion": "N/A",
                    "mensaje": f"El barrio {b_name} registra una concentración inusual de {b_count} incidentes en los últimos 30 días.",
                    "tipo": "HOTSPOT",
                    "valor_actual": b_count,
                    "valor_previo": 0
                })

        return sorted(alertas, key=lambda x: x['nivel'])
