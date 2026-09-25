"""Cartografía: el radar no espera a servidores externos ni deja que una vereda homónima reemplace la oficial."""
import io
import json

import pytest

from services import geocoding_service as geo
from services.geocoding_service import GeocodingService


@pytest.fixture(autouse=True)
def fresh_cache():
    GeocodingService._official_territories.cache_clear()
    yield
    GeocodingService._official_territories.cache_clear()


def test_remote_layers_are_not_queried_by_default(monkeypatch):
    monkeypatch.delenv("SISC_REMOTE_CARTOGRAPHY", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("No debe consultar cartografía remota sin activarla.")

    monkeypatch.setattr(geo, "urlopen", no_network)
    territories = GeocodingService._official_territories()
    assert any(item["source"] == "veredas_jamundi_oficial.geojson" for item in territories.values())


def test_remote_namesake_never_replaces_official_polygon(monkeypatch):
    monkeypatch.setenv("SISC_REMOTE_CARTOGRAPHY", "1")
    local = json.load(open(geo.RURAL_GEOJSON_PATH, encoding="utf-8-sig"))["features"][0]
    namesake = {"type": "Feature", "properties": {"NOMBRE": local["properties"]["Nombre"]},
                "geometry": {"type": "Point", "coordinates": [-74.0, 4.6]}}
    other = {"type": "Feature", "properties": {"NOMBRE": "VEREDA DE OTRO MUNICIPIO"},
             "geometry": {"type": "Point", "coordinates": [-74.0, 4.6]}}
    body = json.dumps({"features": [namesake, other]}).encode()
    monkeypatch.setattr(geo, "urlopen", lambda *a, **k: io.BytesIO(body))
    territories = GeocodingService._official_territories()
    key = GeocodingService.normalize_name(local["properties"]["Nombre"])
    assert territories[key]["source"] == "veredas_jamundi_oficial.geojson"
    assert territories[GeocodingService.normalize_name("VEREDA DE OTRO MUNICIPIO")]["source"] in {"CVC_CATASTRO_VEREDAS", "IGAC_VEREDAS"}
