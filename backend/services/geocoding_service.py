import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple
import unicodedata

from shapely.geometry import shape

logger = logging.getLogger("sisc_geocoding")

GEOJSON_PATH = Path(__file__).resolve().parents[1] / "data" / "barrios_jamundi_valle.geojson"

# Names from SIEDCO that are known to be the same as an official urban polygon.
# Ambiguous names are intentionally not placed on the map.
OFFICIAL_NAME_ALIASES = {
    "TERRANOVA": "CIUDADELA TERRANOVA",
    "SACHAMATE (URB MUNICIPAL)": "SACHAMATE",
}


class GeocodingService:
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize names for reliable matching."""
        if not name:
            return ""
        normalized = "".join(
            char for char in unicodedata.normalize("NFD", name)
            if not unicodedata.combining(char)
        )
        return normalized.upper().strip().replace("  ", " ")

    @staticmethod
    @lru_cache(maxsize=1)
    def _official_representative_points() -> Dict[str, Tuple[float, float]]:
        """Load an interior point for each official Valle urban-neighborhood polygon."""
        if not GEOJSON_PATH.exists():
            logger.warning("Official neighborhood layer was not found: %s", GEOJSON_PATH)
            return {}

        with GEOJSON_PATH.open(encoding="utf-8") as geojson_file:
            features = json.load(geojson_file).get("features", [])

        points = {}
        for feature in features:
            name = feature.get("properties", {}).get("Nombre")
            geometry = feature.get("geometry")
            if not name or not geometry:
                continue
            point = shape(geometry).representative_point()
            points[GeocodingService.normalize_name(name)] = (point.y, point.x)
        return points

    @staticmethod
    def get_coords_for_localidad(localidad: str) -> Optional[Tuple[float, float]]:
        """Return a point inside a verified official urban-neighborhood polygon."""
        normalized = GeocodingService.normalize_name(localidad)
        if not normalized:
            return None

        official_name = OFFICIAL_NAME_ALIASES.get(normalized, normalized)
        return GeocodingService._official_representative_points().get(
            GeocodingService.normalize_name(official_name)
        )

    @staticmethod
    def get_wkt_point(coords: Tuple[float, float]) -> str:
        """Convert (lat, lng) into WKT POINT(lng lat)."""
        lat, lng = coords
        return f"POINT({lng} {lat})"
