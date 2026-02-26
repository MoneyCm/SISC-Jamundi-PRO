import secrets
import datetime
from sqlalchemy.orm import Session
from db.models_intelligence import ReportRun, ReportRecipient, ReportDownloadToken, ReportNotificationLog, ReportDownloadAudit
import logging

logger = logging.getLogger("distribution_service")

class DistributionService:
    @staticmethod
    def generate_secure_token(db: Session, report_run_id: int, expires_in_hours: int = 24):
        """
        Genera un token de acceso seguro y único para un reporte.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=expires_in_hours)
        
        db_token = ReportDownloadToken(
            report_run_id=report_run_id,
            token=token,
            expires_at=expires_at
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        return db_token

    @staticmethod
    def notify_group(db: Session, report_run_id: int, group_name: str, base_url: str):
        """
        Simula el envío de notificaciones a un grupo de destinatarios.
        """
        report = db.query(ReportRun).filter(ReportRun.id == report_run_id).first()
        if not report:
            return {"status": "error", "message": "Report not found"}

        recipients = db.query(ReportRecipient).filter(
            ReportRecipient.group_name == group_name,
            ReportRecipient.is_active == True
        ).all()

        if not recipients:
            return {"status": "skipped", "message": "No active recipients in group"}

        # Generar token de descarga de un solo uso
        token_obj = DistributionService.generate_secure_token(db, report_run_id)
        # Construir enlace seguro usando base_url (si está vacío, usar placeholder)
        base = base_url.rstrip('/') if base_url else 'http://localhost:8000'
        secure_link = f"{base}/api/intelligence/reports/{report_run_id}/export/pdf?token={token_obj.token}"

        success_count = 0
        for rcpt in recipients:
            # Simular envío de email con el enlace seguro
            logger.info(f"Notificando a {rcpt.email} sobre reporte {report.period_key} con link {secure_link}")
            success_count += 1

        # Registrar el log, guardando el enlace en el campo error_detail como placeholder
        log = ReportNotificationLog(
            report_run_id=report_run_id,
            group_name=group_name,
            recipients_count=success_count,
            status="SUCCESS",
            error_detail=secure_link
        )
        db.add(log)
        db.commit()

        return {
            "status": "SUCCESS",
            "recipients": [r.email for r in recipients],
            "secure_link": secure_link,
            "timestamp": log.sent_at.isoformat()
        }

    @staticmethod
    def audit_download(db: Session, report_run_id: int, user_id=None, token_id=None, ip=None):
        """
        Registra una descarga en el log de auditoría.
        """
        audit = ReportDownloadAudit(
            report_run_id=report_run_id,
            user_id=user_id,
            token_id=token_id,
            ip_address=ip
        )
        db.add(audit)
        
        # Incrementar contador en el reporte
        report = db.query(ReportRun).get(report_run_id)
        if report:
            report.download_count = (report.download_count or 0) + 1
            
        db.commit()
        return audit
