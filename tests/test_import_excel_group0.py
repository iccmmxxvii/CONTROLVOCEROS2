import pandas as pd

from core.import_excel import detect_columns, hierarchy_path_from_row, normalize_dataframe


def test_group0_and_hierarchy_levels_are_detected_and_preserved():
    df = pd.DataFrame([
        {
            "COORDINADOR": "Lider Cero",
            "GRUPO 1": "Lider Cero",  # repetición consecutiva: no debe duplicar la ruta
            "GRUPO 2": "Coordinador Dos",
            "GRUPO 3": None,
            "GRUPO 4": "Coordinador Cuatro",
            "GRUPO 5": None,
            "GRUPO 6": None,
            "GRUPO 7": None,
            "VOCEROS": "Persona Promovida",
            "SECCIONESFORM": 123,
            "MUNICIPIOFORM": "AHOME",
        }
    ])

    mapping = detect_columns(df.columns)
    assert mapping["grupo_0"] == "COORDINADOR"
    assert mapping["promovido"] == "VOCEROS"
    assert mapping["seccion"] == "SECCIONESFORM"

    path = hierarchy_path_from_row(df.iloc[0], mapping)
    assert path == ["LIDER CERO", "COORDINADOR DOS", "COORDINADOR CUATRO"]

    normalized, incidents, _ = normalize_dataframe(df)
    row = normalized.iloc[0]
    assert row["grupo_0"] == "LIDER CERO"
    assert row["grupo_1"] == "LIDER CERO"
    assert row["grupo_2"] == "COORDINADOR DOS"
    assert row["grupo_4"] == "COORDINADOR CUATRO"
    assert row["superior_directo"] == "COORDINADOR CUATRO"
    assert row["promovido_normalizado"] == "PERSONA PROMOVIDA"
    assert row["seccion"] == 123
    assert not (incidents["tipo"] == "COLUMNA_FALTANTE").any() if not incidents.empty else True
