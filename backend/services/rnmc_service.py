from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_, or_, desc, text
from db.models_intelligence import RNMCMeasure
from db.models_inspecciones import InspeccionMedida, InspeccionExpediente, InspeccionFinanza, InspeccionActuacion
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
        # 1. Total de Actuaciones (Registros de actividad en el periodo)
        total_records = db.query(InspeccionActuacion).filter(
            InspeccionActuacion.fecha_actuacion >= start_date,
            InspeccionActuacion.fecha_actuacion < end_date
        ).count()
        
        # 2. Top Medidas (Basado en las actuaciones del periodo)
        top_medidas = db.query(
            InspeccionMedida.nombre_medida, func.count(InspeccionActuacion.id).label("total")
        ).join(InspeccionActuacion).filter(
            InspeccionActuacion.fecha_actuacion >= start_date,
            InspeccionActuacion.fecha_actuacion < end_date
        ).group_by(InspeccionMedida.nombre_medida).order_by(desc("total")).limit(5).all()
        
        # 3. Top Estados Actuales de las medidas tocadas en el periodo
        top_estados = db.query(
            InspeccionMedida.estado_actual, func.count(InspeccionMedida.id).label("total")
        ).filter(
            InspeccionMedida.id.in_(
                db.query(InspeccionActuacion.medida_id).filter(
                    InspeccionActuacion.fecha_actuacion >= start_date,
                    InspeccionActuacion.fecha_actuacion < end_date
                )
            )
        ).group_by(InspeccionMedida.estado_actual).order_by(desc("total")).all()
        
        # 4. Pagos y Recaudo
        # Contamos medidas que tuvieron actuación en el periodo y tienen pago registrado
        pagos_count = db.query(InspeccionMedida).join(InspeccionFinanza).filter(
            InspeccionMedida.id.in_(
                db.query(InspeccionActuacion.medida_id).filter(
                    InspeccionActuacion.fecha_actuacion >= start_date,
                    InspeccionActuacion.fecha_actuacion < end_date
                )
            ),
            InspeccionFinanza.valor_pagado > 0
        ).count()
        
        recaudo_sum = db.query(func.sum(InspeccionFinanza.valor_pagado)).filter(
            InspeccionFinanza.medida_id.in_(
                db.query(InspeccionActuacion.medida_id).filter(
                    InspeccionActuacion.fecha_actuacion >= start_date,
                    InspeccionActuacion.fecha_actuacion < end_date
                )
            )
        ).scalar() or 0.0
        
        # 5. Top 5 Localidades (Donde ocurrieron las actuaciones)
        top_localidades = db.query(
            InspeccionExpediente.localidad, func.count(InspeccionActuacion.id).label("total")
        ).join(InspeccionMedida, InspeccionExpediente.id == InspeccionMedida.expediente_id)\
         .join(InspeccionActuacion, InspeccionMedida.id == InspeccionActuacion.medida_id)\
         .filter(
            InspeccionActuacion.fecha_actuacion >= start_date,
            InspeccionActuacion.fecha_actuacion < end_date
        ).group_by(InspeccionExpediente.localidad).order_by(desc("total")).limit(5).all()

        # 6. Estadísticas de Geocode (NUEVO)
        total_exp = db.query(InspeccionExpediente).filter(
            InspeccionExpediente.created_at >= start_date,
            InspeccionExpediente.created_at < end_date
        ).count()
        
        geocoded_exp = db.query(func.count(InspeccionExpediente.id)).filter(
            InspeccionExpediente.created_at >= start_date,
            InspeccionExpediente.created_at < end_date,
            text("geom_punto IS NOT NULL")
        ).scalar()

        return {
            "total_registros": total_records,
            "top_medidas": {m: count for m, count in top_medidas},
            "top_estados": {e: count for e, count in top_estados},
            "pagos_conteo": pagos_count,
            "recaudo_total": float(recaudo_sum),
            "top_localidades": {l: count for l, count in top_localidades},
            "geocoding_stats": {
                "total": total_exp,
                "geocodificados": geocoded_exp,
                "porcentaje": round((geocoded_exp / total_exp * 100), 1) if total_exp > 0 else 0
            },
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
                latest = db.query(func.max(InspeccionActuacion.fecha_actuacion)).scalar()
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
                latest = db.query(func.max(InspeccionActuacion.fecha_actuacion)).scalar()
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
        rezagos = db.query(InspeccionMedida).filter(
            InspeccionMedida.estado_actual == "EN PROCESO",
            InspeccionMedida.dias_duracion >= 30
        ).order_by(desc(InspeccionMedida.dias_duracion)).limit(20).all()

        # 2. Ratificadas sin pago
        impagables = db.query(InspeccionMedida).join(InspeccionFinanza).filter(
            InspeccionMedida.estado_actual == "RATIFICADA",
            or_(InspeccionFinanza.valor_pagado == 0, InspeccionFinanza.valor_pagado == None)
        ).order_by(desc(InspeccionFinanza.valor_neto)).limit(20).all()

        def mask(m):
            exp = m.expediente.numero_expediente
            return {
                "expediente": "***" + exp[-4:] if len(exp) > 4 else exp,
                "medida": m.nombre_medida,
                "dias": m.dias_duracion,
                "valor_neto": float(m.finanza.valor_neto) if m.finanza else 0,
                "fecha_actuacion": m.created_at.strftime("%Y-%m-%d")
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
