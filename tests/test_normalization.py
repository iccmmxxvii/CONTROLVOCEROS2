from core.normalization import normalize_municipality, normalize_name, normalize_phone, normalize_section


def test_name():
    assert normalize_name("  María   José Álvarez ") == "MARIA JOSE ALVAREZ"


def test_phone():
    assert normalize_phone("+52 668-123-4567") == "6681234567"


def test_section():
    assert normalize_section("Sección 0316") == 316


def test_municipality():
    assert normalize_municipality("Culiacán Rosales") == "CULIACAN"


def test_infer_surnames_from_full_name():
    from core.normalization import infer_surnames_from_full_name
    paterno, materno, confianza = infer_surnames_from_full_name("MARIA FERNANDA FELICIAN VEGA")
    assert paterno == "FELICIAN"
    assert materno == "VEGA"
    assert confianza == "ALTA"
