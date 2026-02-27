import httpx
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from db.models_policia import PoliceAsset
from services.scraper_policia import PoliciaScraper

logger = logging.getLogger("police_monitor")

class PoliceMonitorService:
    @staticmethod
    async def check_asset(db: Session, asset: PoliceAsset):
        """
        Realiza un HTTP HEAD para verificar si el archivo ha cambiado.
        """
        try:
            # Desactivar verificación SSL para la Policía (común que tengan certs vencidos o internos)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
                response = await client.head(asset.file_url)
                
                if response.status_code != 200:
                    response = await client.get(asset.file_url, headers={"Range": "bytes=0-0"})

                if response.status_code not in [200, 206]:
                    asset.status = "ERROR"
                    asset.notes = {"error": f"HTTP {response.status_code}", "timestamp": datetime.utcnow().isoformat()}
                    db.commit()
                    return {"status": "ERROR", "detail": f"HTTP {response.status_code}"}

                etag = response.headers.get("ETag")
                last_modified = response.headers.get("Last-Modified")
                content_length = int(response.headers.get("Content-Length", 0))

                changed = False
                if etag and etag != asset.last_seen_etag:
                    changed = True
                elif last_modified and last_modified != asset.last_seen_last_modified:
                    changed = True
                elif content_length and content_length != asset.last_seen_content_length:
                    changed = True

                if changed and asset.status != "UNKNOWN":
                    asset.status = "UPDATED"
                    asset.last_change_detected_at = datetime.utcnow()
                elif not changed:
                    asset.status = "UNCHANGED"

                asset.last_seen_etag = etag
                asset.last_seen_last_modified = last_modified
                asset.last_seen_content_length = content_length
                asset.last_checked_at = datetime.utcnow()
                
                db.commit()
                return {
                    "status": asset.status, 
                    "changed": changed,
                    "etag": etag,
                    "last_modified": last_modified,
                    "size": content_length
                }

        except Exception as e:
            logger.error(f"Error checking police asset {asset.dataset_code}: {e}")
            asset.status = "ERROR"
            asset.notes = {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
            db.commit()
            return {"status": "ERROR", "detail": str(e)}

    @staticmethod
    async def check_all_assets(db: Session):
        assets = db.query(PoliceAsset).all()
        results = {"updated": 0, "unchanged": 0, "error": 0, "total": len(assets)}
        for asset in assets:
            res = await PoliceMonitorService.check_asset(db, asset)
            s = res.get("status")
            if s == "UPDATED": results["updated"] += 1
            elif s == "UNCHANGED": results["unchanged"] += 1
            else: results["error"] += 1
        return results

    @staticmethod
    def seed_initial_assets(db: Session):
        """
        Usa el PoliciaScraper para descubrir y registrar los archivos actuales.
        """
        scraper = PoliciaScraper()
        files = scraper.fetch_available_files()
        
        count = 0
        for f in files:
            # Generar un código único basado en el nombre del archivo
            import re
            code = re.sub(r'[^A-Z0-9]', '_', f['name'].upper())
            
            exists = db.query(PoliceAsset).filter(PoliceAsset.dataset_code == code).first()
            if not exists:
                new_asset = PoliceAsset(
                    dataset_code=code,
                    display_name=f['name'].replace('.xlsx', '').replace('.xls', '').replace('_', ' ').title(),
                    category=f['category'],
                    file_url=f['url'],
                    source_page_url=PoliciaScraper.SOURCE_URL
                )
                db.add(new_asset)
                count += 1
        
        db.commit()
        return count
