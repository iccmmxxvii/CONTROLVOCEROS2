from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.hierarchy import infer_root, resolve_parent_map
from core.import_excel import normalize_dataframe, read_excel_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida un Excel para ICC Control Territorial sin escribir en Supabase.")
    parser.add_argument("excel", type=Path)
    parser.add_argument("--sheet", default=None)
    args = parser.parse_args()

    data = args.excel.read_bytes()
    df, sheets = read_excel_bytes(data, args.sheet)
    normalized, incidents, mapping = normalize_dataframe(df)
    records = normalized.to_dict("records")
    root = infer_root(records)
    _, conflicts = resolve_parent_map(records)

    print(f"Archivo: {args.excel.name}")
    print(f"Hojas: {', '.join(sheets)}")
    print(f"Filas leídas: {len(df)}")
    print(f"Registros normalizados: {len(normalized)}")
    print(f"Personas terminales únicas: {normalized['promovido_normalizado'].nunique() if not normalized.empty else 0}")
    print(f"Secciones únicas: {normalized['seccion'].nunique() if not normalized.empty else 0}")
    print(f"Raíz inferida: {root}")
    print(f"Incidencias: {len(incidents)}")
    print(f"Conflictos jerárquicos: {len(conflicts)}")
    print("\nMapeo:")
    for key, value in mapping.items():
        print(f"  {key}: {value}")
    if conflicts:
        print("\nConflictos jerárquicos:")
        for item in conflicts:
            print(f"  - {item['persona']} -> {item['alternativas']} | elegido: {item['superior_elegido']}")


if __name__ == "__main__":
    main()
