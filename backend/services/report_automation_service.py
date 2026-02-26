import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models_intelligence import NationalCrimeStats, ReportRun
from services.intelligence_service import IntelligenceService
from services.pdf_report_service import PdfReportService
from services.distribution_service import DistributionService
from services.rnmc_service import RNMCService
import json
import os

logger = logging.getLogger("report_automation")

class ReportAutomationService:
    @staticmethod
    def _generate_markdown_table(title, data, columns):
        if not data:
            return f"**{title}**: Sin datos disponibles.\n"
        
        md = f"#### {title}\n"
        md += "| " + " | ".join(columns) + " |\n"
        md += "| " + " | ".join(["---"] * len(columns)) + " |\n"
        
        # Determinar claves del dict basadas en el orden de columnas
        # Conducta | Actual | Anterior | Var_abs | Var_%
        # Entradas suelen ser { "H.PERSONAS": 10, ... }
        
        # Manejo especial para top_conductas y top_barrios
        # actual: {k: v}, anterior: {k: v}
        
        return md

    @staticmethod
    def _format_weekly_markdown(report_data):
        p = report_data["periodo"]
        t = report_data["totales"]
        md = f"### REPORTE SEMANAL - SISC JAMUNDÍ\n"
        md += f"**Periodo**: Semana {p['semana']} de {p['anio']} | **Fecha Corte**: {report_data.get('meta_info', {}).get('fecha_corte', 'N/A')}\n\n"
        
        md += "#### 1. RESUMEN GLOBAL\n"
        md += f"- **Eventos Actual**: {t['actual']}\n"
        md += f"- **Variación WoW**: {t['var_prev_pct']}%  ({'📈' if t['var_prev_pct'] > 0 else '📉'})\n"
        md += f"- **Variación YoY**: {t['var_yoy_pct']}%  ({'📈' if t['var_yoy_pct'] > 0 else '📉'})\n\n"
        
        # Tablas de conductas y barrios (Simplificadas para el log)
        def make_table(title, actual_dict, prev_dict):
            table = f"| {title} | Actual | Anterior | Var_abs | Var_% |\n"
            table += "| --- | --- | --- | --- | --- |\n"
            all_keys = sorted(list(set(actual_dict.keys()) | set(prev_dict.keys())), key=lambda x: actual_dict.get(x, 0), reverse=True)[:5]
            for k in all_keys:
                a = actual_dict.get(k, 0)
                p = prev_dict.get(k, 0)
                diff = a - p
                pct = round((diff/p*100),1) if p > 0 else (100.0 if a > 0 else 0)
                table += f"| {k} | {a} | {p} | {diff} | {pct}% |\n"
            return table

        md += make_table("Conducta", report_data["top_conductas"]["actual"], report_data["top_conductas"]["anterior"]) + "\n"
        md += make_table("Barrio", report_data["top_barrios"]["actual"], report_data["top_barrios"]["anterior"]) + "\n"
        
        return md

    @staticmethod
    def run_weekly_report(db: Session, source_id: str = "SEM_POLICIA", forces=False, forced_by=None, forced_reason=None):
        logger.info(f"Running weekly report for {source_id}...")
        # 1. Detectar última semana
        latest = db.query(NationalCrimeStats.anio, NationalCrimeStats.semana).filter(
            NationalCrimeStats.source_id == source_id
        ).order_by(NationalCrimeStats.anio.desc(), NationalCrimeStats.semana.desc()).first()
        
        if not latest: return None
        
        anio, semana = latest.anio, latest.semana
        period_key = f"{anio}-W{semana:02d}"
        
        # 2. Verificar bloqueo
        existing = db.query(ReportRun).filter(
            ReportRun.report_type == "SEMANAL",
            ReportRun.source_id == source_id,
            ReportRun.period_key == period_key
        ).first()
        
        if existing and not forces:
            logger.info(f"Reporte semanal {period_key} ya existe. Saltando.")
            return existing

        # 3. Generar
        raw_data = IntelligenceService.get_comparison(db, source_id, type="weekly", value={"anio": anio, "semana": semana})
        report_json = IntelligenceService.format_comparison_report(raw_data)
        
        # Fecha corte real
        fc = db.query(func.max(NationalCrimeStats.fecha_hecho)).filter(
            NationalCrimeStats.source_id == source_id,
            NationalCrimeStats.anio == anio,
            NationalCrimeStats.semana == semana
        ).scalar()
        report_json["meta_info"] = {"fecha_corte": fc.isoformat() if fc else None}

        md = ReportAutomationService._format_weekly_markdown(report_json)
        
        if existing:
            existing.output_json = report_json
            existing.output_markdown = md
            existing.generated_at = datetime.utcnow()
            existing.status = "COMPLETED"
            existing.forced = forces
            existing.forced_by = forced_by
            existing.forced_reason = forced_reason
            db.commit()
            return existing
        else:
            # Crear nuevo reporte
            new_run = ReportRun(
                report_type="SEMANAL",
                source_id=source_id,
                period_key=period_key,
                status="COMPLETED",
                output_json=report_json,
                output_markdown=md,
                meta_info=report_json["meta_info"],
                forced=forces,
                forced_by=forced_by,
                forced_reason=forced_reason
            )
            db.add(new_run)
            # Generar PDF si aún no existe
            if not new_run.pdf_path:
                PdfReportService.generate_pdf(db, new_run)
            # Determinar grupo según tipo de reporte
            target_group = "comite_semanal" if new_run.report_type == "SEMANAL" else "consejo_mensual"
            # Evitar notificar si ya existe un log exitoso para este reporte y grupo
            existing_log = db.query(ReportNotificationLog).filter(
                ReportNotificationLog.report_run_id == new_run.id,
                ReportNotificationLog.group_name == target_group,
                ReportNotificationLog.status == "SUCCESS"
            ).first()
            if not existing_log:
                base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
                DistributionService.notify_group(db, new_run.id, target_group, base_url)
            db.commit()
            return new_run


    @staticmethod
    def run_monthly_report(db: Session, source_id: str = "SEM_POLICIA", forces=False, forced_by=None, forced_reason=None):
        latest = db.query(NationalCrimeStats.anio, NationalCrimeStats.mes).filter(
            NationalCrimeStats.source_id == source_id
        ).order_by(NationalCrimeStats.anio.desc(), NationalCrimeStats.mes.desc()).first()
        
        if not latest: return None
        
        anio, mes = latest.anio, latest.mes
        period_key = f"{anio}-M{mes:02d}"
        
        existing = db.query(ReportRun).filter(
            ReportRun.report_type == "MENSUAL",
            ReportRun.source_id == source_id,
            ReportRun.period_key == period_key
        ).first()
        
        if existing and not forces: return existing

        raw_data = IntelligenceService.get_comparison(db, source_id, type="monthly", value={"anio": anio, "mes": mes})
        report_json = IntelligenceService.format_comparison_report(raw_data)
        
        fc = db.query(func.max(NationalCrimeStats.fecha_hecho)).filter(
            NationalCrimeStats.source_id == source_id,
            NationalCrimeStats.anio == anio,
            NationalCrimeStats.mes == mes
        ).scalar()
        report_json["meta_info"] = {"fecha_corte": fc.isoformat() if fc else None}

        md = f"### REPORTE MENSUAL - SISC JAMUNDÍ\nPeriodo: Mes {mes} de {anio}\n\n"
        md += f"**Resumen**: {report_json['totales']['actual']} eventos (Var MoM: {report_json['totales']['var_prev_pct']}%)\n"

        if existing:
            existing.output_json = report_json
            existing.output_markdown = md
            existing.status = "COMPLETED"
            existing.forced = forces
            existing.forced_by = forced_by
            existing.forced_reason = forced_reason
            db.commit()
            return existing
        else:
            new_run = ReportRun(
                report_type="MENSUAL",
                source_id=source_id,
                period_key=period_key,
                status="COMPLETED",
                output_json=report_json,
                output_markdown=md,
                meta_info=report_json["meta_info"],
                forced=forces,
                forced_by=forced_by,
                forced_reason=forced_reason
            )
            db.add(new_run)
            db.commit()
            return new_run

    @staticmethod
    def _format_rnmc_markdown(report_data):
        a = report_data["actual"]
        p = report_data["period_key"]
        md = f"### REPORTE RNMC - MEDIDAS GESTIONADAS\n"
        md += f"**Periodo**: {p} | **Fecha Inicio**: {a['periodo']['inicio']} | **Fecha Fin**: {a['periodo']['fin']}\n\n"
        
        md += "#### 1. RESUMEN DE GESTIÓN (KPIs)\n"
        md += f"- **Total Medidas Registradas**: {a['total_registros']}\n"
        md += f"- **Pagos Identificados**: {a['pagos_conteo']}\n"
        md += f"- **Recaudo Total Validado**: ${a['recaudo_total']:,.2f}\n"
        if "porcentaje_pagado" in a:
            md += f"- **Efectividad de Recaudo**: {a['porcentaje_pagado']}%\n"
            
        if "especificos" in a:
            e = a["especificos"]
            md += "\n#### 2. ESTADOS DE PROCEDIMIENTOS\n"
            md += f"- **En Proceso de Gestión**: {e.get('en_proceso', 0)}\n"
            md += f"- **Medidas Ratificadas**: {e.get('ratificada', 0)}\n"
            md += f"- **Pagos Confirmados (Estado)**: {e.get('pagado', 0)}\n"

        md += "\n#### 3. TOP 5 MEDIDAS MÁS FRECUENTES\n"
        md += "| Medida | Total |\n| --- | --- |\n"
        for m, count in list(a["top_medidas"].items())[:5]:
            md += f"| {m} | {count} |\n"
            
        md += "\n#### 4. DISTRIBUCIÓN POR LOCALIDAD\n"
        md += "| Localidad | Registros |\n| --- | --- |\n"
        for l, count in list(a["top_localidades"].items())[:5]:
            md += f"| {l} | {count} |\n"

        # 5. Seccion de Alertas (Crítico para Inspección)
        if "alertas" in a:
            al = a["alertas"]
            md += "\n#### 5. ALERTAS CRÍTICAS DE GESTIÓN\n"
            
            # Subseccion 5.1: Rezagos
            md += "\n**5.1 Medidas EN PROCESO con > 30 días (Top 20)**\n"
            if al.get("rezago_proceso"):
                md += "| Expediente | Medida | Días | Fecha Actuación |\n| --- | --- | --- | --- |\n"
                for item in al["rezago_proceso"]:
                    md += f"| {item['expediente']} | {item['medida']} | {item['dias']} | {item['fecha_actuacion']} |\n"
            else:
                md += "*No se detectaron rezagos críticos.*\n"

            # Subseccion 5.2: Impagos Ratificados
            md += "\n**5.2 Medidas RATIFICADAS Pendientes de Pago (Top 20)**\n"
            if al.get("impagos_ratificados"):
                md += "| Expediente | Medida | Valor Neto | Fecha Actuación |\n| --- | --- | --- | --- |\n"
                for item in al["impagos_ratificados"]:
                    md += f"| {item['expediente']} | {item['medida']} | ${item['valor_neto']:,.0f} | {item['fecha_actuacion']} |\n"
            else:
                md += "*No se detectaron ratificaciones sin pago pendiente.*\n"
                
        return md

    @staticmethod
    def run_rnmc_report(db: Session, report_type: str = "SEMANAL", anio=None, valor=None, forces=False):
        """
        Genera reporte automático para RNMC.
        """
        mode = "weekly" if report_type == "SEMANAL" else "monthly"
        if report_type == "YTD": mode = "ytd"
        
        raw_data = RNMCService.get_rnmc_comparison(db, mode=mode, anio=anio, valor=valor)
        if not raw_data: return None
        
        period_key = raw_data["period_key"]
        source_id = "INSPECCION_MEDIDAS_RNMC"
        
        existing = db.query(ReportRun).filter(
            ReportRun.report_type == report_type,
            ReportRun.source_id == source_id,
            ReportRun.period_key == period_key
        ).first()
        
        if existing and not forces: return existing
        
        md = ReportAutomationService._format_rnmc_markdown(raw_data)
        
        if existing:
            existing.output_json = raw_data
            existing.output_markdown = md
            existing.generated_at = datetime.utcnow()
            db.commit()
            return existing
        else:
            new_run = ReportRun(
                report_type=report_type,
                source_id=source_id,
                period_key=period_key,
                status="COMPLETED",
                output_json=raw_data,
                output_markdown=md,
                meta_info={"generated_by": "automation"}
            )
            db.add(new_run)
            db.commit()
            db.refresh(new_run)
            # Generar PDF
            PdfReportService.generate_pdf(db, new_run)
            return new_run
