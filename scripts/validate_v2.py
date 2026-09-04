from __future__ import annotations

import sys
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cartography import enrich_normalized_with_cartography, load_section_catalog
from core.hierarchy import infer_root, resolve_parent_map
from core.import_excel import normalize_dataframe, read_excel_bytes


def main(path: str):
    data=Path(path).read_bytes()
    raw,_=read_excel_bytes(data)
    norm,inc,_=normalize_dataframe(raw)
    enriched,tinc=enrich_normalized_with_cartography(norm)
    _,conf=resolve_parent_map(enriched.to_dict("records"))
    print(f"Filas Excel: {len(raw):,}")
    print(f"Registros normalizados: {len(norm):,}")
    print(f"Promovidos únicos: {norm['promovido_normalizado'].nunique():,}")
    print(f"Secciones en Excel: {norm['seccion'].nunique():,}")
    print(f"Secciones cartografía V2: {len(load_section_catalog()):,}")
    print(f"Registros con sección localizada: {(enriched['estado_catalogo']=='CARTOGRAFIA_PRECARGADA').sum():,}")
    print(f"Registros con sección no localizada: {(enriched['estado_catalogo']=='NO_LOCALIZADA').sum():,}")
    print(f"Incidencias importación: {len(inc):,}")
    print(f"Incidencias territoriales: {len(tinc):,}")
    print(f"Raíz inferida: {infer_root(enriched.to_dict('records'))}")
    print(f"Conflictos jerárquicos: {len(conf):,}")


if __name__=='__main__':
    if len(sys.argv)<2:
        raise SystemExit("Uso: python scripts/validate_v2.py archivo.xlsx")
    main(sys.argv[1])
