import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.request import Request, urlopen
import unicodedata

from shapely.geometry import shape

logger = logging.getLogger("sisc_geocoding")

GEOJSON_PATH = Path(__file__).resolve().parents[1] / "data" / "barrios_jamundi_valle.geojson"
EXTRA_GEOJSON_PATH = Path(__file__).resolve().parents[1] / "data" / "barrios_jamundi_valle_extra.geojson"
RURAL_GEOJSON_PATH = Path(__file__).resolve().parents[1] / "data" / "veredas_jamundi_oficial.geojson"
OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "data" / "barrios_official_aliases.json"
REMOTE_GEOJSON_URLS = [
    ("CVC_CATASTRO_VEREDAS", "https://geo.cvc.gov.co/arcgis/rest/services/TERRITORIAL_ADMINISTRATIVA/Catastro_Alcaldia_Jamundi/FeatureServer/3/query?where=1%3D1&outFields=%2A&returnGeometry=true&outSR=4326&f=geojson"),
    ("IGAC_VEREDAS", "https://sigi.igac.gov.co/hosted/rest/services/Veredas/FeatureServer/0/query?where=1%3D1&outFields=%2A&returnGeometry=true&outSR=4326&f=geojson"),
]

# Names from SIEDCO that are known to be the same as an official urban-neighborhood polygon.
# Ambiguous names are intentionally not placed on the map.
OFFICIAL_NAME_ALIASES = {
    "TERRANOVA": "CIUDADELA TERRANOVA",
    "SACHAMATE (URB MUNICIPAL)": "SACHAMATE",
    "VILLA PAZ": "VIILA PAZ",
    "LA PRADERA I": "LA PRADERA",
}


def _normalize_aliases_payload(payload) -> Dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    result = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        result[GeocodingService.normalize_name(key)] = value
    return result


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
    def _load_aliases() -> Dict[str, str]:
        """Load optional name overrides loaded from a JSON file."""
        aliases = dict(OFFICIAL_NAME_ALIASES)
        if not OVERRIDES_PATH.exists():
            return aliases

        try:
            with OVERRIDES_PATH.open(encoding="utf-8-sig") as aliases_file:
                data = json.load(aliases_file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo cargar aliases desde %s: %s", OVERRIDES_PATH, exc)
            return aliases

        file_aliases = _normalize_aliases_payload(data)
        aliases.update(file_aliases)
        return aliases

    @staticmethod
    def _iter_geojson_paths() -> list[Path]:
        paths = [GEOJSON_PATH]
        env_paths = os.getenv("SISC_EXTRA_GEOJSON_PATHS", "").strip()
        if env_paths:
            for path_raw in env_paths.split(","):
                path = Path(path_raw.strip())
                if path:
                    paths.append(path)
        if EXTRA_GEOJSON_PATH.exists():
            paths.append(EXTRA_GEOJSON_PATH)
        if RURAL_GEOJSON_PATH.exists():
            paths.append(RURAL_GEOJSON_PATH)
        return paths

    @staticmethod
    @lru_cache(maxsize=1)
    def _official_territories() -> Dict[str, Dict]:
        """Load official urban and rural polygons, retaining each source for traceability."""
        territories = {}

        def add_features(features, source):
            for feature in features or []:
                properties = feature.get("properties") or {}
                name = properties.get("Nombre") or properties.get("NOMBRE") or properties.get("nombre") or properties.get("name")
                geometry = feature.get("geometry")
                if not name or not geometry:
                    continue
                point = shape(geometry).representative_point()
                territories[GeocodingService.normalize_name(name)] = {
                    "geometry": geometry,
                    "coords": (point.y, point.x),
                    "source": source,
                }

        for geojson_path in GeocodingService._iter_geojson_paths():
            if not geojson_path.exists():
                logger.debug("Official neighborhood layer not found: %s", geojson_path)
                continue
            try:
                with geojson_path.open(encoding="utf-8-sig") as geojson_file:
                    add_features(json.load(geojson_file).get("features", []), geojson_path.name)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("No se pudo cargar cartografia %s: %s", geojson_path, exc)

        for source, url in REMOTE_GEOJSON_URLS:
            try:
                request = Request(url, headers={"Accept": "application/geo+json, application/json"})
                with urlopen(request, timeout=4) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                add_features(payload.get("features", []), source)
                logger.info("Cartografia remota cargada: %s", source)
            except Exception as exc:
                logger.warning("No se pudo consultar cartografia remota %s: %s", source, exc)

        if not territories:
            logger.warning("Official neighborhood layer was not found or empty: %s", GEOJSON_PATH)
        return territories

    @staticmethod
    def get_official_territory(localidad: str) -> Optional[Dict]:
        """Return verified official geometry and an interior reference point for a territory."""
        normalized = GeocodingService.normalize_name(localidad)
        if not normalized:
            return None

        aliases = GeocodingService._load_aliases()
        territories = GeocodingService._official_territories()
        candidates = [normalized]
        for prefix in ("CGTO ", "CGTO DE ", "CORREGIMIENTO ", "CORREGIMIENTO DE ", "VEREDA ", "VDA "):
            if normalized.startswith(prefix):
                candidates.append(normalized[len(prefix):].strip())
        for candidate in candidates:
            official_name = aliases.get(candidate, candidate)
            territory = territories.get(GeocodingService.normalize_name(official_name))
            if territory:
                return territory
        return None

    @staticmethod
    def get_coords_for_localidad(localidad: str) -> Optional[Tuple[float, float]]:
        """Return a point inside a verified official urban-neighborhood polygon."""
        territory = GeocodingService.get_official_territory(localidad)
        return territory["coords"] if territory else None

    @staticmethod
    def get_wkt_point(coords: Tuple[float, float]) -> str:
        """Convert (lat, lng) into WKT POINT(lng lat)."""
        lat, lng = coords
        return f"POINT({lng} {lat})"
