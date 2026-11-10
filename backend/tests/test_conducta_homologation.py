from services.conducta_homologation import homologar_conducta_policia


def test_police_penal_article_conductas_are_homologated():
    cases = {
        "ARTÍCULO 103. HOMICIDIO": ("Homicidio", "HOMICIDIO"),
        "ARTÍCULO 111. LESIONES PERSONALES": ("Lesiones personales", "LESIONES"),
        "ARTÍCULO 239. HURTO PERSONAS": ("Hurto a personas", "HURTO"),
        "ARTÍCULO 239. HURTO RESIDENCIAS": ("Hurto a residencias", "HURTO"),
        "ARTÍCULO 239. HURTO ENTIDADES COMERCIALES": ("Hurto a comercio", "HURTO"),
        "ARTÍCULO 239. HURTO MOTOCICLETAS": ("Hurto a motocicletas", "HURTO"),
        "ARTÍCULO 239. HURTO AUTOMOTORES": ("Hurto a automotores", "HURTO"),
    }

    for raw, expected in cases.items():
        conducta, categoria, matched = homologar_conducta_policia(raw)
        assert (conducta, categoria) == expected
        assert matched is True


def test_police_weekly_abbreviated_hurtos_are_homologated():
    cases = {
        "H.PERSONAS": ("Hurto a personas", "HURTO"),
        "H.MOTOS": ("Hurto a motocicletas", "HURTO"),
        "H.AUTOMOTORES": ("Hurto a automotores", "HURTO"),
        "H.RESIDENCIAS": ("Hurto a residencias", "HURTO"),
        "H.COMERCIO": ("Hurto a comercio", "HURTO"),
        "h. personas": ("Hurto a personas", "HURTO"),
        "PERSONAS": ("Hurto a personas", "HURTO"),
        "MOTOCICLETAS": ("Hurto a motocicletas", "HURTO"),
        "AUTOMOTORES": ("Hurto a automotores", "HURTO"),
    }

    for raw, expected in cases.items():
        conducta, categoria, matched = homologar_conducta_policia(raw)
        assert (conducta, categoria) == expected, raw
        assert matched is True


def test_bare_words_inside_other_text_are_not_hurtos():
    conducta, _categoria, matched = homologar_conducta_policia("TRATA DE PERSONAS")
    assert conducta == "Delito General" and matched is False
