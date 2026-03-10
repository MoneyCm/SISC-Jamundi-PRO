import os
import hashlib
import datetime
from markdown2 import markdown
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    print(f"[AVISO] WeasyPrint no disponible: {e}")
    WEASYPRINT_AVAILABLE = False
from sqlalchemy.orm import Session
from db.models_intelligence import ReportRun
import logging

logger = logging.getLogger("pdf_service")

class PdfReportService:
    @staticmethod
    def generate_pdf(db: Session, report: ReportRun, user_name: str = "SYSTEM"):
        """
        Genera un PDF a partir de un ReportRun y lo persiste.
        """
        # 1. Preparar Carpeta de Exportación
        base_dir = "exports/reports"
        os.makedirs(base_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Reporte_{report.report_type}_{user_name}_{timestamp}.pdf"
        file_path = os.path.join(base_dir, filename)
        
        # 2. Calcular Hash de Integridad
        content_hash = hashlib.sha256(report.output_markdown.encode('utf-8')).hexdigest()
        
        # 3. Preparar HTML
        html_content = PdfReportService._build_html(report, content_hash, user_name)
        
        # 4. Generar PDF con WeasyPrint
        if not WEASYPRINT_AVAILABLE:
            logger.error("No se puede generar PDF: WeasyPrint no está instalado o faltan librerías de sistema.")
            report.pdf_path = "ERROR_NO_WEASYPRINT"
            db.commit()
            return None

        css = CSS(string=f"""
            @page {{ 
                size: A4; margin: 2cm; 
                @bottom-right {{
                    content: "Exportado por: {user_name} | SISC Jamundí";
                    font-size: 8pt;
                    color: #cbd5e1;
                }}
            }}
            body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #334155; line-height: 1.5; font-size: 11pt; }}
            .header {{ border-bottom: 2px solid #1e293b; padding-bottom: 10px; margin-bottom: 30px; text-align: center; }}
            .header h1 {{ color: #1e293b; font-size: 20pt; margin: 0; text-transform: uppercase; }}
            .header p {{ margin: 5px 0 0; font-size: 10pt; color: #64748b; font-style: italic; }}
            
            h3 {{ color: #1e293b; border-left: 4px solid #4f46e5; padding-left: 10px; margin-top: 25px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 10pt; }}
            th {{ background-color: #f1f5f9; color: #475569; font-weight: bold; text-align: left; padding: 10px; border: 1px solid #e2e8f0; }}
            td {{ padding: 10px; border: 1px solid #e2e8f0; }}
            
            .audit-seal {{ margin-top: 50px; padding: 20px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 9pt; }}
            .audit-seal h4 {{ margin: 0 0 10px; font-size: 10pt; text-transform: uppercase; color: #475569; border-bottom: 1px solid #cbd5e1; padding-bottom: 5px; }}
            .audit-line {{ display: flex; justify-content: space-between; margin-bottom: 4px; }}
            .audit-label {{ color: #64748b; font-weight: bold; }}
            .audit-value {{ color: #1e293b; font-family: monospace; }}
            
            .forced-alert {{ color: #b45309; background-color: #fffbeb; padding: 10px; border: 1px solid #fde68a; margin-top: 10px; border-radius: 4px; }}
            .watermark {{ position: fixed; bottom: -1.5cm; left: 0; font-size: 7pt; color: #94a3b8; }}
        """)
        
        HTML(string=html_content).write_pdf(file_path, stylesheets=[css])
        
        # 5. Actualizar Registro en DB
        report.pdf_path = file_path
        report.pdf_sha256 = content_hash
        report.pdf_generated_at = datetime.datetime.utcnow()
        db.commit()
        
        return file_path

    @staticmethod
    def _build_html(report: ReportRun, content_hash: str, user_name: str):
        # Convertir Markdown a HTML
        body_html = markdown(report.output_markdown)
        
        forced_html = ""
        if report.forced:
            forced_html = f"""
            <div class="forced-alert">
                <strong>ATENCIÓN: REPORTE GENERADO MANUALMENTE (OVERRIDE)</strong><br/>
                Por: {report.forced_by or 'N/A'}<br/>
                Razón: {report.forced_reason or 'N/A'}
            </div>
            """
            
        audit_seal = f"""
        <div class="audit-seal">
            <h4>Sello de Evidencia Digital - SISC Jamundí</h4>
            <div class="audit-line"><span class="audit-label">UUID Reporte:</span> <span class="audit-value">{report.id}</span></div>
            <div class="audit-line"><span class="audit-label">Generado por:</span> <span class="audit-value">{user_name}</span></div>
            <div class="audit-line"><span class="audit-label">Periodo:</span> <span class="audit-value">{report.period_key}</span></div>
            <div class="audit-line"><span class="audit-label">Fecha Exportación (UTC):</span> <span class="audit-value">{datetime.datetime.utcnow().isoformat()}</span></div>
            <div class="audit-line"><span class="audit-label">Hash Integridad (SHA256):</span> <span class="audit-value">{content_hash}</span></div>
            {forced_html}
        </div>
        """
        
        full_html = f"""
        <html>
            <body data-user="{user_name}">
                <div class="header">
                    <h1>SISC Jamundí: Inteligencia Estratégica</h1>
                    <p>Alcaldía de Jamundí - Secretaría de Gobierno - Observatorio del Delito</p>
                </div>
                <div class="content">
                    {body_html}
                </div>
                {audit_seal}
                <div class="watermark">Documento Producido por SISC Jamundí - Uso Institucional para {user_name}</div>
            </body>
        </html>
        """
        return full_html
