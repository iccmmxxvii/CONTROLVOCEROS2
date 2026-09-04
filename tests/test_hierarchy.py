from core.hierarchy import infer_root, resolve_parent_map


def test_hierarchy_parent_map():
    rows = [
        {"ruta_jerarquica": "RANDY > ANA", "promovido_normalizado": "LUIS"},
        {"ruta_jerarquica": "RANDY > ANA", "promovido_normalizado": "MARIA"},
        {"ruta_jerarquica": "RANDY > ANA > LUIS", "promovido_normalizado": "PEDRO"},
    ]
    assert infer_root(rows) == "RANDY"
    parent_map, conflicts = resolve_parent_map(rows)
    assert parent_map["ANA"] == "RANDY"
    assert parent_map["LUIS"] == "ANA"
    assert parent_map["PEDRO"] == "LUIS"
    assert conflicts == []
