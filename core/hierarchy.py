from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


def split_path(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(">") if x and x.strip()]


def hierarchy_edges(records: Iterable[Dict[str, Any]]) -> List[Tuple[str, str, int]]:
    counts: Counter[Tuple[str, str]] = Counter()
    for record in records:
        path = split_path(record.get("ruta_jerarquica"))
        terminal = record.get("promovido_normalizado")
        full = path + ([terminal] if terminal else [])
        compact: List[str] = []
        for name in full:
            if name and (not compact or compact[-1] != name):
                compact.append(name)
        for parent, child in zip(compact, compact[1:]):
            if parent != child:
                counts[(parent, child)] += 1
    return [(p, c, n) for (p, c), n in counts.items()]


def resolve_parent_map(records: Iterable[Dict[str, Any]]) -> Tuple[Dict[str, Optional[str]], List[Dict[str, Any]]]:
    edges = hierarchy_edges(records)
    candidates: Dict[str, Counter[str]] = defaultdict(Counter)
    all_nodes = set()
    roots = Counter()

    for record in records:
        path = split_path(record.get("ruta_jerarquica"))
        terminal = record.get("promovido_normalizado")
        if path:
            roots[path[0]] += 1
        all_nodes.update(path)
        if terminal:
            all_nodes.add(terminal)

    for parent, child, count in edges:
        candidates[child][parent] += count

    root = roots.most_common(1)[0][0] if roots else None
    parent_map: Dict[str, Optional[str]] = {node: None for node in all_nodes}
    conflicts: List[Dict[str, Any]] = []

    for child, options in candidates.items():
        ranked = options.most_common()
        chosen = ranked[0][0]
        parent_map[child] = chosen
        if len(ranked) > 1:
            conflicts.append({
                "persona": child,
                "superior_elegido": chosen,
                "alternativas": "; ".join(f"{p} ({n})" for p, n in ranked),
                "criterio": "mayor frecuencia en las rutas del Excel",
            })

    if root:
        parent_map[root] = None

    # Corte simple de ciclos: si A->B y B->A, conservar la relación más próxima a la raíz inferida.
    for node in list(parent_map):
        seen = set()
        current = node
        while current and current not in seen:
            seen.add(current)
            current = parent_map.get(current)
        if current in seen and current is not None:
            conflicts.append({
                "persona": node,
                "superior_elegido": None,
                "alternativas": "ciclo detectado",
                "criterio": "relación anulada para evitar ciclo",
            })
            parent_map[node] = None

    return parent_map, conflicts


def infer_root(records: Iterable[Dict[str, Any]]) -> Optional[str]:
    roots = Counter()
    for record in records:
        path = split_path(record.get("ruta_jerarquica"))
        if path:
            roots[path[0]] += 1
    return roots.most_common(1)[0][0] if roots else None
