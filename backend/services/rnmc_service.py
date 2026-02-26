from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_, or_, desc
from db.models_intelligence import RNMCMeasure
from datetime import datetime, timedelta
import pandas as pd

class RNMCService:
    @staticmethod
    def get_weekly_stats(db: Session, anio: int, semana: int):
        # Filtrar por semana (usando extract(isoyear/isoweek) o directamente fecha_actuacion)
        # Para mayor precisión usamos rangos de fecha
        # Suponiendo que la semana empieza en Lunes
        d = f"{anio}-W{semana}"
        start_date = datetime.strptime(d + '-1', "%G-W%V-%u")
        end_date = start_date + timedelta(days=7)
        
        return RNMCService._get_stats_for_range(db, start_date, end_date)

    @staticmethod
    def get_monthly_stats(db: Session, anio: int, mes: int):
        start_date = datetime(anio, mes, 1)
        if mes == 12:
            end_date = datetime(anio + 1, 1, 1)
        else:
            end_date = datetime(anio, mes + 1, 1)
            
        return RNMCService._get_stats_for_range(db, start_date, end_date)

    @staticmethod
    def get_ytd_stats(db: Session, anio: int):
        start_date = datetime(anio, 1, 1)
        end_date = datetime.now() if anio == datetime.now().year else datetime(anio, 12, 31, 23, 59, 59)
        
        return RNMCService._get_stats_for_range(db, start_date, end_date)

    @staticmethod
    def _get_stats_for_range(db: Session, start_date: datetime, end_date: datetime):
        base_query = db.query(RNMCMeasure).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date
        )
        
        total_records = base_query.count()
        
        top_medidas = db.query(
            RNMCMeasure.medida, func.count(RNMCMeasure.id).label("total")
        ).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date
        ).group_by(RNMCMeasure.medida).order_by(desc("total")).limit(5).all()
        
        top_estados = db.query(
            RNMCMeasure.estado, func.count(RNMCMeasure.id).label("total")
        ).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date
        ).group_by(RNMCMeasure.estado).order_by(desc("total")).all()
        
        pagos_count = db.query(RNMCMeasure).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date,
            RNMCMeasure.fecha_pago != None
        ).count()
        
        recaudo_sum = db.query(func.sum(RNMCMeasure.valor_pagado)).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date
        ).scalar() or 0.0
        
        # Top 5 Localidades (Volumen)
        top_localidades = db.query(
            RNMCMeasure.localidad, func.count(RNMCMeasure.id).label("total")
        ).filter(
            RNMCMeasure.fecha_actuacion >= start_date,
            RNMCMeasure.fecha_actuacion < end_date
        ).group_by(RNMCMeasure.localidad).order_by(desc("total")).limit(5).all()

        return {
            "total_registros": total_records,
            "top_medidas": {m: count for m, count in top_medidas},
            "top_estados": {e: count for e, count in top_estados},
            "pagos_conteo": pagos_count,
            "recaudo_total": float(recaudo_sum),
            "top_localidades": {l: count for l, count in top_localidades},
            "periodo": {
                "inicio": start_date.strftime("%Y-%m-%d"),
                "fin": (end_date - timedelta(seconds=1)).strftime("%Y-%m-%d")
            }
        }

    @staticmethod
    def get_rnmc_comparison(db: Session, mode="weekly", anio=None, valor=None):
        if not anio:
            anio = datetime.now().year
            
        if mode == "weekly":
            if not valor:
                # Buscar última semana con datos
                latest = db.query(func.max(RNMCMeasure.fecha_actuacion)).scalar()
                if not latest: return None
                anio = latest.year
                valor = latest.isocalendar()[1]
            
            actual = RNMCService.get_weekly_stats(db, anio, valor)
            
            # WoW
            prev_week_date = datetime.strptime(f"{anio}-W{valor}-1", "%G-W%V-%u") - timedelta(days=7)
            prev_y, prev_w, _ = prev_week_date.isocalendar()
            prev = RNMCService.get_weekly_stats(db, prev_y, prev_w)
            
            # YoY
            yoy = RNMCService.get_weekly_stats(db, anio - 1, valor)
            
            # % pagado
            pct_pagado = (actual["pagos_conteo"] / actual["total_registros"] * 100) if actual["total_registros"] > 0 else 0
            actual["porcentaje_pagado"] = round(pct_pagado, 1)
            
            # Estados especificos
            actual["especificos"] = {
                "en_proceso": actual["top_estados"].get("EN PROCESO", 0),
                "ratificada": actual["top_estados"].get("RATIFICADA", 0),
                "no_impuesta": actual["top_estados"].get("NO IMPUESTA", 0),
                "pagado": actual["top_estados"].get("PAGADO", 0)
            }

            # Alertas
            actual["alertas"] = RNMCService._get_alerts(db)

            return {
                "mode": "weekly",
                "actual": actual,
                "prev": prev,
                "yoy": yoy,
                "period_key": f"{anio}-W{valor:02d}"
            }
            
        elif mode == "monthly":
            if not valor:
                latest = db.query(func.max(RNMCMeasure.fecha_actuacion)).scalar()
                if not latest: return None
                anio = latest.year
                valor = latest.month
                
            actual = RNMCService.get_monthly_stats(db, anio, valor)
            
            # MoM
            if valor == 1:
                prev = RNMCService.get_monthly_stats(db, anio - 1, 12)
            else:
                prev = RNMCService.get_monthly_stats(db, anio, valor - 1)
                
            # YoY
            yoy = RNMCService.get_monthly_stats(db, anio - 1, valor)
            
            # % pagado
            pct_pagado = (actual["pagos_conteo"] / actual["total_registros"] * 100) if actual["total_registros"] > 0 else 0
            actual["porcentaje_pagado"] = round(pct_pagado, 1)
            
            # Especificos solicitado: en_proceso, ratificada, no_impuesta
            especificos = {
                "en_proceso": actual["top_estados"].get("EN PROCESO", 0),
                "ratificada": actual["top_estados"].get("RATIFICADA", 0),
                "no_impuesta": actual["top_estados"].get("NO IMPUESTA", 0),
                "pagado": actual["top_estados"].get("PAGADO", 0)
            }
            actual["especificos"] = especificos
            actual["alertas"] = RNMCService._get_alerts(db)
            
            return {
                "mode": "monthly",
                "actual": actual,
                "prev": prev,
                "yoy": yoy,
                "period_key": f"{anio}-M{valor:02d}"
            }

        elif mode == "ytd":
            actual = RNMCService.get_ytd_stats(db, anio)
            yoy = RNMCService.get_ytd_stats(db, anio - 1)
            
            # Alertas (Reutilizando helper)
            actual["alertas"] = RNMCService._get_alerts(db)

            return {
                "mode": "ytd",
                "actual": actual,
                "yoy": yoy,
                "period_key": f"{anio}-YTD"
            }

    @staticmethod
    def _get_alerts(db: Session):
        """
        Helper para alertas criticas de RNMC.
        1. EN PROCESO > 30 días
        2. RATIFICADA sin pago
        """
        from sqlalchemy import or_
        # 1. Rezago en Proceso
        rezagos = db.query(RNMCMeasure).filter(
            RNMCMeasure.estado == "EN PROCESO",
            RNMCMeasure.dias >= 30
        ).order_by(desc(RNMCMeasure.dias)).limit(20).all()

        # 2. Ratificadas sin pago
        impagables = db.query(RNMCMeasure).filter(
            RNMCMeasure.estado == "RATIFICADA",
            or_(RNMCMeasure.valor_pagado == 0, RNMCMeasure.valor_pagado == None)
        ).order_by(desc(RNMCMeasure.valor_neto)).limit(20).all()

        def mask(m):
            exp = str(m.expediente)
            return {
                "expediente": "***" + exp[-4:] if len(exp) > 4 else exp,
                "medida": m.medida,
                "dias": m.dias,
                "valor_neto": m.valor_neto,
                "fecha_actuacion": m.fecha_actuacion.strftime("%Y-%m-%d")
            }

        return {
            "rezago_proceso": [mask(r) for r in rezagos],
            "impagos_ratificados": [mask(i) for i in impagables]
        }

    @staticmethod
    def get_backlog(db: Session, from_date=None, to_date=None, min_dias=None, estado=None, medida=None, localidad=None, page=1, page_size=50):
        query = db.query(RNMCMeasure)
        
        if from_date:
            query = query.filter(RNMCMeasure.fecha_actuacion >= from_date)
        if to_date:
            query = query.filter(RNMCMeasure.fecha_actuacion <= to_date)
        if min_dias:
            query = query.filter(RNMCMeasure.dias >= min_dias)
        if estado:
            query = query.filter(RNMCMeasure.estado == estado)
        if medida:
            query = query.filter(RNMCMeasure.medida == medida)
        if localidad:
            query = query.filter(RNMCMeasure.localidad == localidad)
            
        total = query.count()
        items = query.order_by(desc(RNMCMeasure.fecha_actuacion)).offset((page-1)*page_size).limit(page_size).all()
        
        results = []
        for i in items:
            exp = str(i.expediente)
            masked = "********" + exp[-4:] if len(exp) > 4 else exp
            results.append({
                "id": i.id,
                "fecha_actuacion": i.fecha_actuacion.strftime("%Y-%m-%d"),
                "localidad": i.localidad,
                "medida": i.medida,
                "estado": i.estado,
                "dias": i.dias,
                "valor_neto": i.valor_neto,
                "valor_pagado": i.valor_pagado,
                "event_fingerprint": i.event_fingerprint,
                "source_id": i.source_id,
                "expediente_masked": masked
            })
            
        return {"total": total, "items": results, "page": page, "page_size": page_size}

    @staticmethod
    def get_measure_history(db: Session, source_id: str, event_fingerprint: str):
        from db.models_intelligence import RNMCStatusHistory
        
        current = db.query(RNMCMeasure).filter(
            RNMCMeasure.source_id == source_id,
            RNMCMeasure.event_fingerprint == event_fingerprint
        ).first()
        
        if not current:
            return None
            
        history = db.query(RNMCStatusHistory).filter(
            RNMCStatusHistory.source_id == source_id,
            RNMCStatusHistory.event_fingerprint == event_fingerprint
        ).order_by(RNMCStatusHistory.changed_at.asc()).all()
        
        return {
            "current": {
                "medida": current.medida,
                "expediente_masked": "***" + str(current.expediente)[-4:] if current.expediente else "N/A",
                "estado": current.estado,
                "fecha_actuacion": current.fecha_actuacion.strftime("%Y-%m-%d"),
                "valor_neto": current.valor_neto,
                "valor_pagado": current.valor_pagado or 0
            },
            "history": [
                {
                    "estado_anterior": h.estado_anterior,
                    "estado_nuevo": h.estado_nuevo,
                    "changed_at": h.changed_at.isoformat(),
                    "fuente_archivo": h.fuente_archivo,
                    "ingestion_id": str(h.ingestion_id) if h.ingestion_id else None
                } for h in history
            ]
        }

    @staticmethod
    def get_series(db: Session, mode="month", periods=12):
        results = []
        now = datetime.now()
        
        if mode == "month":
            for i in range(periods):
                target_date = now - timedelta(days=30*i)
                anio, mes = target_date.year, target_date.month
                stats = RNMCService.get_monthly_stats(db, anio, mes)
                results.append({
                    "period": f"{anio}-{mes:02d}",
                    "total": stats["total_registros"],
                    "pagadas": stats["pagos_conteo"],
                    "recaudo": stats["recaudo_total"]
                })
        else: # weekly
            for i in range(periods):
                target_date = now - timedelta(weeks=i)
                anio, sem, _ = target_date.isocalendar()
                stats = RNMCService.get_weekly_stats(db, anio, sem)
                results.append({
                    "period": f"{anio}-W{sem:02d}",
                    "total": stats["total_registros"],
                    "pagadas": stats["pagos_conteo"],
                    "recaudo": stats["recaudo_total"]
                })
        
        return list(reversed(results))
