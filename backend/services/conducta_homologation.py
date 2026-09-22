import re
import unicodedata


def normalize_conducta_key(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def normalize_conducta_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def homologar_conducta_policia(conducta_raw, catalogo=None):
    """
    Homologa conductas SIEDCO/PONAL, incluyendo denominaciones con articulo penal.
    Retorna (valor_estandar, categoria_delito, matched).
    """
    val = normalize_conducta_text(conducta_raw)
    compact = normalize_conducta_key(conducta_raw)
    catalogo = catalogo or {}

    if val in catalogo:
        c = catalogo[val]
        return c.valor_estandar, c.categoria_delito, True
    if compact in catalogo:
        c = catalogo[compact]
        return c.valor_estandar, c.categoria_delito, True

    if "HOMICIDIO" in val or "MUERTE" in val:
        return "Homicidio", "HOMICIDIO", True
    if "LESIONES" in val or "HERIDO" in val:
        return "Lesiones personales", "LESIONES", True

    if "HURTO" in val or "ROBO" in val:
        if "PERSONA" in val:
            return "Hurto a personas", "HURTO", True
        if "RESIDENCIA" in val:
            return "Hurto a residencias", "HURTO", True
        if "COMERCIO" in val or "ENTIDADES COMERCIALES" in val:
            return "Hurto a comercio", "HURTO", True
        if "AUTO" in val or "VEHICULO" in val or "VEHICULO" in compact:
            return "Hurto a automotores", "HURTO", True
        if "MOTO" in val:
            return "Hurto a motocicletas", "HURTO", True
        return "Hurto (Otros)", "HURTO", True

    if "VIOLENCIA" in val and "INTRAFAMILIAR" in val:
        return "Violencia intrafamiliar", "VIF", True
    if "EXTORSION" in val:
        return "Extorsion", "EXTORSION", True
    if "SECUESTRO" in val:
        return "Secuestro", "SECUESTRO", True

    return "Delito General", "OTROS", False
