from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_
from db.models_intelligence import NationalCrimeStats
from datetime import datetime, timedelta
import pandas as pd

class IntelligenceService:
    @staticmethod
    def get_stats_by_period(db: Session, source_id: str, anio: int, semana: int = None, mes: int = None):
        filters = [NationalCrimeStats.source_id == source_id, NationalCrimeStats.anio == anio]
        if semana:
            filters.append(NationalCrimeStats.semana == semana)
        if mes:
            filters.append(NationalCrimeStats.mes == mes)
            
        data = db.query(
            NationalCrimeStats.tipo_delito,
            NationalCrimeStats.barrio,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(and_(*filters)).group_by(
            NationalCrimeStats.tipo_delito, NationalCrimeStats.barrio
        ).all()
        
        return data

    @staticmethod
    def get_comparison(db: Session, source_id: str, type="weekly", value=None):
        """
        type: 'weekly', 'monthly', 'annual'
        value: {'anio': 2026, 'semana': 8} or {'anio': 2026, 'mes': 2}
        """
        if not value:
            # Buscar último periodo disponible
            latest = db.query(NationalCrimeStats.anio, NationalCrimeStats.semana, NationalCrimeStats.mes).filter(
                NationalCrimeStats.source_id == source_id
            ).order_by(NationalCrimeStats.anio.desc(), NationalCrimeStats.fecha_hecho.desc()).first()
            if not latest: return None
            value = {"anio": latest.anio, "semana": latest.semana, "mes": latest.mes}

        anio = value['anio']
        
        if type == "weekly":
            semana = value['semana']
            actual_data = IntelligenceService.get_stats_by_period(db, source_id, anio, semana=semana)
            
            # WoW
            from sqlalchemy import or_
            prev_week = db.query(NationalCrimeStats.anio, NationalCrimeStats.semana).filter(
                NationalCrimeStats.source_id == source_id,
                or_(
                    NationalCrimeStats.anio < anio,
                    and_(NationalCrimeStats.anio == anio, NationalCrimeStats.semana < semana)
                )
            ).order_by(NationalCrimeStats.anio.desc(), NationalCrimeStats.semana.desc()).first()
            
            wow_data = IntelligenceService.get_stats_by_period(db, source_id, prev_week.anio, semana=prev_week.semana) if prev_week else []
            yoy_data = IntelligenceService.get_stats_by_period(db, source_id, anio - 1, semana=semana)
            
            return {
                "actual": {"anio": anio, "semana": semana, "data": actual_data},
                "prev": {"anio": int(prev_week.anio) if prev_week else None, "semana": int(prev_week.semana) if prev_week else None, "data": wow_data},
                "yoy": {"anio": anio - 1, "semana": semana, "data": yoy_data},
                "mode": "weekly"
            }
            
        elif type == "monthly":
            mes = value['mes']
            actual_data = IntelligenceService.get_stats_by_period(db, source_id, anio, mes=mes)
            
            # MoM
            from sqlalchemy import or_
            prev_month = db.query(NationalCrimeStats.anio, NationalCrimeStats.mes).filter(
                NationalCrimeStats.source_id == source_id,
                or_(
                    NationalCrimeStats.anio < anio,
                    and_(NationalCrimeStats.anio == anio, NationalCrimeStats.mes < mes)
                )
            ).order_by(NationalCrimeStats.anio.desc(), NationalCrimeStats.mes.desc()).first()
            
            mom_data = IntelligenceService.get_stats_by_period(db, source_id, prev_month.anio, mes=prev_month.mes) if prev_month else []
            yoy_data = IntelligenceService.get_stats_by_period(db, source_id, anio - 1, mes=mes)
            
            return {
                "actual": {"anio": anio, "mes": mes, "data": actual_data},
                "prev": {"anio": int(prev_month.anio) if prev_month else None, "mes": int(prev_month.mes) if prev_month else None, "data": mom_data},
                "yoy": {"anio": anio - 1, "mes": mes, "data": yoy_data},
                "mode": "monthly"
            }

    @staticmethod
    def get_stats_by_range(db: Session, source_id: str, start_date: datetime, end_date: datetime):
        data = db.query(
            NationalCrimeStats.tipo_delito,
            NationalCrimeStats.barrio,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(
            NationalCrimeStats.source_id == source_id,
            NationalCrimeStats.fecha_hecho >= start_date,
            NationalCrimeStats.fecha_hecho <= end_date
        ).group_by(
            NationalCrimeStats.tipo_delito, NationalCrimeStats.barrio
        ).all()
        return data

    @staticmethod
    def get_ytd_comparison(db: Session, source_id: str, anio: int = None):
        if not anio:
            latest = db.query(func.max(NationalCrimeStats.anio)).filter(NationalCrimeStats.source_id == source_id).scalar()
            anio = latest or datetime.now().year
            
        latest_date = db.query(func.max(NationalCrimeStats.fecha_hecho)).filter(
            NationalCrimeStats.source_id == source_id, NationalCrimeStats.anio == anio
        ).scalar()
        
        if not latest_date: return None
        
        # Normalizar a datetime si es date
        if isinstance(latest_date, type(datetime.now().date())):
            latest_date = datetime.combine(latest_date, datetime.min.time())
            
        day = latest_date.day
        month = latest_date.month
        
        # Rango Actual
        start_actual = datetime(anio, 1, 1)
        end_actual = latest_date
        data_actual = IntelligenceService.get_stats_by_range(db, source_id, start_actual, end_actual)
        
        # Rango Anterior
        start_prev = datetime(anio - 1, 1, 1)
        end_prev = datetime(anio - 1, month, day)
        data_prev = IntelligenceService.get_stats_by_range(db, source_id, start_prev, end_prev)
        
        def summarize_ytd(data_list):
            df = pd.DataFrame(data_list, columns=["conducta", "barrio", "total"])
            if df.empty: return 0, {}, {}
            return (
                int(df["total"].sum()),
                df.groupby("conducta")["total"].sum().sort_values(ascending=False).head(5).to_dict(),
                df.groupby("barrio")["total"].sum().sort_values(ascending=False).head(5).to_dict()
            )

        total_a, c_a, b_a = summarize_ytd(data_actual)
        total_p, c_p, b_p = summarize_ytd(data_prev)
        
        # Alerta de Cobertura
        def check_coverage_ytd(start, end):
            days_with_data = db.query(func.count(func.distinct(NationalCrimeStats.fecha_hecho))).filter(
                NationalCrimeStats.source_id == source_id,
                NationalCrimeStats.fecha_hecho >= start,
                NationalCrimeStats.fecha_hecho <= end
            ).scalar() or 0
            total_days = (end - start).days + 1
            return (days_with_data / total_days) * 100 if total_days > 0 else 0

        cov_a = check_coverage_ytd(start_actual, end_actual)
        cov_p = check_coverage_ytd(start_prev, end_prev)
        
        alerta = None
        if cov_a < 80 or cov_p < 80:
            alerta = f"ALERTA_COBERTURA: Datos parciales détectados (Actual: {cov_a:.1f}%, Anterior: {cov_p:.1f}%)"

        return {
            "periodo_ytd": {
                "anio_actual": anio,
                "anio_anterior": anio - 1,
                "fecha_corte": latest_date.strftime("%Y-%m-%d")
            },
            "totales": {
                "actual": total_a,
                "anterior": total_p,
                "variacion_abs": total_a - total_p,
                "variacion_pct": round(((total_a - total_p) / total_p * 100), 1) if total_p > 0 else 0
            },
            "top_conductas": {
                "actual": {str(k): int(v) for k, v in c_a.items()},
                "anterior": {str(k): int(v) for k, v in c_p.items()}
            },
            "top_barrios": {
                "actual": {str(k): int(v) for k, v in b_a.items()},
                "anterior": {str(k): int(v) for k, v in b_p.items()}
            },
            "cobertura": {
                "actual_pct": round(cov_a, 1),
                "anterior_pct": round(cov_p, 1),
                "alerta": alerta
            }
        }

    @staticmethod
    def get_multi_year_accumulated(db: Session, source_id: str, start_mm_dd: str, end_mm_dd: str):
        """
        Calcula el acumulado de un periodo (ej. '01-01' a '02-21') para todos los años disponibles.
        """
        all_years = db.query(func.distinct(NationalCrimeStats.anio)).filter(
            NationalCrimeStats.source_id == source_id
        ).all()
        
        results = {}
        for (y,) in all_years:
            start = datetime.strptime(f"{y}-{start_mm_dd}", "%Y-%m-%d")
            end = datetime.strptime(f"{y}-{end_mm_dd}", "%Y-%m-%d")
            total = db.query(func.sum(NationalCrimeStats.cantidad)).filter(
                NationalCrimeStats.source_id == source_id,
                NationalCrimeStats.fecha_hecho >= start,
                NationalCrimeStats.fecha_hecho <= end
            ).scalar() or 0
            results[int(y)] = int(total)
            
        return results

    @staticmethod
    def format_comparison_report(result):
        if not result: return "No hay datos para comparar."
        
        def summarize(data_list):
            df = pd.DataFrame(data_list, columns=["conducta", "barrio", "total"])
            if df.empty: return 0, {}, {}
            total = df["total"].sum()
            top_conductas = df.groupby("conducta")["total"].sum().sort_values(ascending=False).head(5).to_dict()
            top_barrios = df.groupby("barrio")["total"].sum().sort_values(ascending=False).head(5).to_dict()
            return total, top_conductas, top_barrios

        t_actual, c_actual, b_actual = summarize(result["actual"]["data"])
        t_prev, c_prev, b_prev = summarize(result["prev"]["data"])
        t_yoy, c_yoy, b_yoy = summarize(result["yoy"]["data"])
        
        # Nota de cobertura
        cobertura = "completa"
        if t_prev == 0 or t_yoy == 0:
            cobertura = "parcial (faltan datos históricos en base)"

        def var(a, b):
            if b == 0: return 100.0 if a > 0 else 0.0
            return round(((a - b) / b) * 100, 1)

        summary = {
            "periodo": {k: (int(v) if hasattr(v, "item") else v) for k, v in result["actual"].items() if k != "data"},
            "metatada": result["mode"],
            "cobertura": cobertura,
            "totales": {
                "actual": int(t_actual),
                "anterior": int(t_prev),
                "yoy": int(t_yoy),
                "var_prev_pct": var(t_actual, t_prev),
                "var_yoy_pct": var(t_actual, t_yoy)
            },
            "top_conductas": {
                "actual": {str(k): int(v) for k, v in c_actual.items()},
                "anterior": {str(k): int(v) for k, v in c_prev.items()},
                "yoy": {str(k): int(v) for k, v in c_yoy.items()}
            },
            "top_barrios": {
                "actual": {str(k): int(v) for k, v in b_actual.items()},
                "anterior": {str(k): int(v) for k, v in b_prev.items()},
                "yoy": {str(k): int(v) for k, v in b_yoy.items()}
            }
        }
        return summary
