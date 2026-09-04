# ICC Control Territorial V3.2 — Entrega funcional

Versión: `3.2.0`

## Mejora principal

Motor de asignación de casilla con tres estados: EXACTA/AUTOMÁTICA, SUGERIDA y PENDIENTE. Las sugerencias nunca se mezclan con los datos exactos en reportes o exportaciones.

## Reportes

- Grupo 0.
- Cobertura por municipio, distrito y sección.
- Secciones con/sin presencia.
- Casillas: promovidos exactos, sugeridos y pendientes.
- Exportación ejecutiva Excel y CSV por panel.

## Rendimiento y control

- Base precargada: 12,211 registros.
- Índice de casillas por sección para evitar búsquedas repetidas.
- 20 pruebas automatizadas aprobadas.
- No se inventan asignaciones extraordinarias sin localidad ni rangos oficiales inexistentes; en esos casos la salida permanece pendiente o sugerida según corresponda.
