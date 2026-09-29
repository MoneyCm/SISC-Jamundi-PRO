from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_, or_, desc, text
from db.models_inspecciones import InspeccionMedida, InspeccionExpediente, InspeccionFinanza, InspeccionActuacion
from datetime import date, datetime, timedelta
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

    # La tabla rnmc_measures ya no se carga: la lista sale de las tablas de Inspecciones, que reciben
    # los reportes del RNMC. El "event_fingerprint" de cada fila es el id de la medida.
    SOURCE_INSPECCIONES = "INSPECCIONES"

    @staticmethod
    def _medidas_query(db: Session):
        from sqlalchemy import func as sa_func
        primera = (db.query(InspeccionActuacion.medida_id.label("medida_id"),
                            sa_func.min(InspeccionActuacion.fecha_actuacion).label("fecha"))
                   .group_by(InspeccionActuacion.medida_id).subquery())
        query = (db.query(InspeccionMedida, InspeccionExpediente, InspeccionFinanza, primera.c.fecha)
                 .join(InspeccionExpediente, InspeccionExpediente.id == InspeccionMedida.expediente_id)
                 .join(primera, primera.c.medida_id == InspeccionMedida.id)
                 .outerjoin(InspeccionFinanza, InspeccionFinanza.medida_id == InspeccionMedida.id))
        return query, primera

    @staticmethod
    def _fila(medida, expediente, finanza, fecha):
        numero = str(expediente.numero_expediente or "")
        inicio = medida.fecha_inicio or (fecha.date() if fecha else None)
        return {
            "id": str(medida.id),
            "fecha_actuacion": fecha.strftime("%Y-%m-%d") if fecha else None,
            "localidad": expediente.localidad,
            "medida": medida.nombre_medida,
            "estado": medida.estado_actual,
            "dias": (date.today() - inicio).days if inicio else None,
            "valor_neto": float(finanza.valor_neto or 0) if finanza else 0.0,
            "valor_pagado": float(finanza.valor_pagado or 0) if finanza else 0.0,
            "event_fingerprint": str(medida.id),
            "source_id": RNMCService.SOURCE_INSPECCIONES,
            "expediente_masked": "********" + numero[-4:] if len(numero) > 4 else numero,
        }

    @staticmethod
    def get_backlog(db: Session, from_date=None, to_date=None, min_dias=None, estado=None, medida=None, localidad=None, page=1, page_size=50):
        query, primera = RNMCService._medidas_query(db)
        if from_date:
            query = query.filter(primera.c.fecha >= from_date)
        if to_date:
            query = query.filter(primera.c.fecha <= to_date)
        if min_dias:
            limite = date.today() - timedelta(days=int(min_dias))
            query = query.filter(func.coalesce(InspeccionMedida.fecha_inicio, func.date(primera.c.fecha)) <= limite)
        if estado:
            query = query.filter(InspeccionMedida.estado_actual == estado)
        if medida:
            query = query.filter(InspeccionMedida.nombre_medida == medida)
        if localidad:
            query = query.filter(InspeccionExpediente.localidad == localidad)

        total = query.count()
        items = query.order_by(desc(primera.c.fecha)).offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "items": [RNMCService._fila(*item) for item in items], "page": page, "page_size": page_size}

    @staticmethod
    def get_measure_history(db: Session, source_id: str, event_fingerprint: str):
        import uuid as uuid_module
        try:
            medida_id = uuid_module.UUID(str(event_fingerprint))
        except ValueError:
            return None
        query, _primera = RNMCService._medidas_query(db)
        item = query.filter(InspeccionMedida.id == medida_id).first()
        if not item:
            return None
        fila = RNMCService._fila(*item)
        # Las actuaciones de la medida, en orden: la fecha y el archivo del que salió cada una.
        actuaciones = (db.query(InspeccionActuacion.fecha_actuacion, InspeccionActuacion.fuente_archivo)
                       .filter(InspeccionActuacion.medida_id == medida_id)
                       .order_by(InspeccionActuacion.fecha_actuacion.asc()).all())
        return {
            "current": {key: fila[key] for key in ("medida", "expediente_masked", "estado", "fecha_actuacion", "valor_neto", "valor_pagado")},
            "history": [
                {"estado_anterior": "", "estado_nuevo": "REGISTRO EN RNMC",
                 "changed_at": fecha.isoformat() if fecha else None, "fuente_archivo": fuente}
                for fecha, fuente in actuaciones
            ],
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
