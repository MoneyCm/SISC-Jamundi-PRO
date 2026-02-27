import requests
import re
import urllib3
import logging
import sys
import os

# Ajustar path para importar desde backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models_mindefensa import MindefensaAsset

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("mindefensa_discovery")

class MindefensaDiscoveryService:
    SOURCE_URL = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    ASSET_BASE_URL = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/{id}/native/{filename}"

    @staticmethod
    def _map_filename_to_code(filename):
        fn = filename.upper()
        if "HOMICIDIO" in fn and "INTENCIONAL" in fn: return "HOMICIDIO_INTENCIONAL"
        if "HURTO" in fn and "PERSONAS" in fn: return "HURTO_PERSONAS"
        if "HURTO" in fn and "A COMERCIO" in fn or "HURTO" in fn and "COMERCIO" in fn: return "HURTO_COMERCIO"
        if "HURTO" in fn and "A RESIDENCIAS" in fn or "HURTO" in fn and "RESIDENCIAS" in fn: return "HURTO_RESIDENCIAS"
        if "LESIONES" in fn and "COMUNES" in fn: return "LESIONES_COMUNES"
        if "SEXUALES" in fn: return "DELITOS_SEXUALES"
        if "VIOLENCIA" in fn and "INTRAFAMILIAR" in fn: return "VIOLENCIA_INTRAFAMILIAR"
        if "SECUESTRO" in fn: return "SECUESTRO"
        if "EXTORSI" in fn: return "EXTORSION"
        if "TERRORISMO" in fn: return "TERRORISMO"
        if "MASACRES" in fn: return "MASACRES"
        return None

    @staticmethod
    def discover_and_update():
        db = SessionLocal()
        print(f"🔍 Iniciando auto-descubrimiento en {MindefensaDiscoveryService.SOURCE_URL}...")
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            r = requests.get(MindefensaDiscoveryService.SOURCE_URL, headers=headers, verify=False, timeout=30)
            html = r.text
            
            # 1. Buscar todos los bloques de assets (Oracle CMS usa JSON incrustado)
            # El patrón suele ser "contentId":"CONT...", "imageHrefName":"Nombre.xlsx"
            asset_matches = re.findall(r'\"contentId\":\"(CONT.*?)\".*?\"imageHrefName\":\"(.*?\.xlsx)\"', html)
            
            if not asset_matches:
                # Intento alternativo
                asset_matches = re.findall(r'\"(CONT.*?)\".*?\"(.*?\.xlsx)\"', html)

            print(f"📦 Encontrados {len(asset_matches)} activos potenciales en la página.")

            updates = 0
            for asset_id, filename in asset_matches:
                dataset_code = MindefensaDiscoveryService._map_filename_to_code(filename)
                
                if dataset_code:
                    asset = db.query(MindefensaAsset).filter(MindefensaAsset.dataset_code == dataset_code).first()
                    if asset:
                        filename_enc = filename.replace(" ", "%20")
                        new_url = MindefensaDiscoveryService.ASSET_BASE_URL.replace("{id}", asset_id).replace("{filename}", filename_enc)
                        
                        if asset.file_url != new_url:
                            print(f"✅ Actualizando {dataset_code}: {filename}")
                            asset.file_url = new_url
                            asset.status = "UNKNOWN"
                            db.add(asset)
                            updates += 1
                else:
                    # Log para ver qué archivos no estamos mapeando
                    print(f"❓ Archivo no mapeado: {filename}")
            
            db.commit()
            print(f"🚀 Finalizado. Se actualizaron {updates} URLs.")
            return updates

        except Exception as e:
            print(f"❌ Error durante descubrimiento: {e}")
            import traceback
            traceback.print_exc()
            return 0
        finally:
            db.close()

if __name__ == "__main__":
    MindefensaDiscoveryService.discover_and_update()
