import httpx
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from db.models_mindefensa import MindefensaAsset

logger = logging.getLogger("mindefensa_monitor")

class MindefensaMonitorService:
    @staticmethod
    async def check_asset(db: Session, asset: MindefensaAsset):
        """
        Realiza un HTTP HEAD para verificar si el archivo ha cambiado.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.head(asset.file_url)
                
                if response.status_code != 200:
                    # Algunos servidores no soportan HEAD bien, intentar GET parcial
                    response = await client.get(asset.file_url, headers={"Range": "bytes=0-0"})

                if response.status_code not in [200, 206]:
                    asset.status = "ERROR"
                    asset.notes = {"error": f"HTTP {response.status_code}", "timestamp": datetime.utcnow().isoformat()}
                    db.commit()
                    return {"status": "ERROR", "detail": f"HTTP {response.status_code}"}

                etag = response.headers.get("ETag")
                last_modified = response.headers.get("Last-Modified")
                content_length = int(response.headers.get("Content-Length", 0))

                # Lógica de detección de cambios
                changed = False
                if etag and etag != asset.last_seen_etag:
                    changed = True
                elif last_modified and last_modified != asset.last_seen_last_modified:
                    changed = True
                elif content_length and content_length != asset.last_seen_content_length:
                    # Fallback si ETag y Last-Modified son inestables o faltan
                    changed = True

                if changed and asset.status != "UNKNOWN":
                    asset.status = "UPDATED"
                    asset.last_change_detected_at = datetime.utcnow()
                elif not changed:
                    asset.status = "UNCHANGED"

                # Actualizar metadatos
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
            logger.error(f"Error checking asset {asset.dataset_code}: {e}")
            asset.status = "ERROR"
            asset.notes = {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
            db.commit()
            return {"status": "ERROR", "detail": str(e)}

    @staticmethod
    async def check_all_assets(db: Session):
        assets = db.query(MindefensaAsset).all()
        results = {
            "updated": 0,
            "unchanged": 0,
            "error": 0,
            "total": len(assets)
        }
        
        for asset in assets:
            res = await MindefensaMonitorService.check_asset(db, asset)
            status = res.get("status")
            if status == "UPDATED":
                results["updated"] += 1
            elif status == "UNCHANGED":
                results["unchanged"] += 1
            else:
                results["error"] += 1
                
        return results

    @staticmethod
    def seed_initial_assets(db: Session):
        """
        Puebla la base de datos con los assets oficiales de MinDefensa.
        """
        base_url = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica/documents/"
        source_page = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
        
        datasets = [
            # VIDA E INTEGRIDAD
            ("HOMICIDIO_INTENCIONAL", "Homicidio Intencional", "VIDA E INTEGRIDAD", "homicidio_intencional.xlsx"),
            ("HOMICIDIO_TRANSITO", "Homicidio Accidentes Tránsito", "VIDA E INTEGRIDAD", "homicidios_transito.xlsx"),
            ("LESIONES_COMUNES", "Lesiones Comunes", "VIDA E INTEGRIDAD", "lesiones_comunes.xlsx"),
            ("LESIONES_TRANSITO", "Lesiones Accidentes Tránsito", "VIDA E INTEGRIDAD", "lesiones_transito.xlsx"),
            ("MASACRES", "Masacres", "VIDA E INTEGRIDAD", "masacres.xlsx"),
            
            # PATRIMONIO ECONÓMICO
            ("HURTO_PERSONAS", "Hurto a Personas", "PATRIMONIO", "hurto_personas.xlsx"),
            ("HURTO_COMERCIO", "Hurto a Comercio", "PATRIMONIO", "hurto_comercio.xlsx"),
            ("HURTO_RESIDENCIAS", "Hurto a Residencias", "PATRIMONIO", "hurto_residencias.xlsx"),
            ("HURTO_VEHICULOS", "Hurto de Vehículos", "PATRIMONIO", "hurto_vehiculos.xlsx"),
            ("EXTORSION", "Extorsión", "PATRIMONIO", "extorsion.xlsx"),
            ("PIRATERIA_TERRESTRE", "Piratería Terrestre", "PATRIMONIO", "pirateria_terrestre.xlsx"),
            
            # LIBERTAD Y OTROS
            ("SECUESTRO", "Secuestro", "LIBERTAD", "secuestro.xlsx"),
            ("VIOLENCIA_INTRAFAMILIAR", "Violencia Intrafamiliar", "FAMILIA", "violencia_intrafamiliar.xlsx"),
            ("DELITOS_SEXUALES", "Delitos Sexuales", "SEXUAL", "delitos_sexuales.xlsx"),
            ("DELITOS_INFORMATICOS", "Delitos Informáticos", "INFORMÁTICA", "delitos_informaticos.xlsx"),
            
            # DROGAS / NARCOTRÁFICO
            ("INCAUTACION_COCAINA", "Incautación de Cocaína", "NARCOTRÁFICO", "incautacion_cocaina.xlsx"),
            ("INCAUTACION_MARIHUANA", "Incautación de Marihuana", "NARCOTRÁFICO", "incautacion_marihuana.xlsx"),
            ("ERRADICACION", "Erradicación", "NARCOTRÁFICO", "erradicacion.xlsx"),
            ("DESTRUCCION_INFRAESTRUCTURA", "Destrucción Infraestructura", "NARCOTRÁFICO", "destruccion_infraestructuras.xlsx"),
            
            # SEGURIDAD PÚBLICA
            ("TERRORISMO", "Terrorismo", "SEGURIDAD", "terrorismo.xlsx"),
            ("VOLADURA_OLEODUCTOS", "Voladura de Oleoductos", "SEGURIDAD", "voladura_oleoductos.xlsx"),
            
            # OTROS
            ("AFECTACION_FUERZA_PUBLICA", "Afectación Fuerza Pública", "FUERZA PÚBLICA", "afectacion_fuerza_publica.xlsx"),
        ]
        
        for code, name, cat, filename in datasets:
            exists = db.query(MindefensaAsset).filter(MindefensaAsset.dataset_code == code).first()
            if not exists:
                new_asset = MindefensaAsset(
                    dataset_code=code,
                    display_name=name,
                    category=cat,
                    file_url=f"{base_url}{filename}",
                    source_page_url=source_page
                )
                db.add(new_asset)
        
        db.commit()
