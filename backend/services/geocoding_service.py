import logging
from typing import Tuple, Optional, Dict
import unicodedata

logger = logging.getLogger("sisc_geocoding")

# Mapeo de Localidades/Barrios a Coordenadas (Centroides aproximados) para Jamundí
JAMUNDI_GEO_MAPPING: Dict[str, Tuple[float, float]] = {
    # ZONA URBANA - COMUNAS
    "CENTRO": (3.2612, -76.5365),
    "EL RODEO": (3.2645, -76.5312),
    "PORTAL DE JORDAN": (3.2505, -76.5412),
    "ALFEREZ REAL": (3.2534, -76.5389),
    "LA PRADERA": (3.2588, -76.5422),
    "BONANZA": (3.2678, -76.5211),
    "TERRANOVA": (3.2712, -76.5188),
    "CIUDAD SUR": (3.2455, -76.5455),
    "VIA CALI JAMUNDI": (3.2753, -76.5281),
    
    # CORREGIMIENTOS
    "POTRERITO": (3.2412, -76.5822),
    "VILLA PAZ": (3.2211, -76.4855),
    "ROZO": (3.2344, -76.5122),
    "QUILCA CE": (3.2155, -76.5566),
    "SAN ISIDRO": (3.2655, -76.5988),
    "TIMBA": (3.1122, -76.5777), # Límite con Cauca
}

class GeocodingService:
    @staticmethod
    def normalize_name(name: str) -> str:
        """Limpia el nombre del barrio para búsqueda robusta."""
        if not name: return ""
        # Quitar tildes y normalizar
        name = "".join(c for c in unicodedata.normalize('NFD', name) if not unicodedata.combining(c))
        # Mayúsculas, quitar caracteres extra y trim
        return name.upper().strip().replace("  ", " ")

    @staticmethod
    def get_coords_for_localidad(localidad: str) -> Optional[Tuple[float, float]]:
        """
        Retorna (lat, lng) para una localidad de Jamundí.
        Si no encuentra coincidencia exacta, intenta búsqueda parcial.
        """
        norm_name = GeocodingService.normalize_name(localidad)
        if not norm_name:
            return None

        # Búsqueda exacta
        if norm_name in JAMUNDI_GEO_MAPPING:
            return JAMUNDI_GEO_MAPPING[norm_name]

        # Búsqueda parcial / difusa básica
        for key, coords in JAMUNDI_GEO_MAPPING.items():
            if key in norm_name or norm_name in key:
                logger.info(f"Geocoding: Coincidencia parcial '{norm_name}' -> '{key}'")
                return coords

        logger.warning(f"Geocoding: No se encontraron coordenadas para '{localidad}'")
        return None

    @staticmethod
    def get_wkt_point(coords: Tuple[float, float]) -> str:
        """Convierte (lat, lng) a WKT POINT(lng lat)"""
        lat, lng = coords
        return f"POINT({lng} {lat})"
