import requests
import argparse
import os
import logging
from datetime import datetime

from core.config import is_strong_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cron_reports")

# Configuración por defecto
API_BASE = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("SISC_REPORT_TRIGGER_KEY")

def run_trigger(args):
    if not is_strong_secret(API_KEY):
        raise RuntimeError("SISC_REPORT_TRIGGER_KEY debe estar configurada para ejecutar reportes automaticos.")

    url = f"{API_BASE}/api/intelligence/reports/trigger"
    payload = {
        "type": args.type,
        "source_id": args.source_id,
        "force": args.force,
        "forced_by": args.forced_by,
        "forced_reason": args.forced_reason
    }
    
    headers = {
        "X-API-KEY": API_KEY
    }
    
    logger.info(f"Enviando trigger a {url} para tipo='{args.type}'...")
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            logger.info(f"SUCCESS: {resp.json()}")
        else:
            logger.error(f"FAILURE: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"CONNECTION ERROR: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger SISC Automated Reports")
    parser.add_argument("--type", default="all", choices=["all", "weekly", "monthly"], help="Report type")
    parser.add_argument("--source_id", default="SEM_POLICIA", help="Data source ID")
    parser.add_argument("--force", action="store_true", help="Force regeneration of report")
    parser.add_argument("--forced_by", default="SYSTEM_CRON", help="Who triggered the force")
    parser.add_argument("--forced_reason", default="Scheduled execution", help="Reason for forcing")
    
    args = parser.parse_args()
    run_trigger(args)
