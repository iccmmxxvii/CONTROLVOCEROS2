# Arquitectura V1

## Regla principal

La persona no tiene un `GRUPO 1/2/3/4` fijo. Se almacena su `superior_directo_id`. La vista recursiva calcula el nivel desde la raíz de cada estructura.

## Flujo Excel

`Excel original → RAW → normalización → incidencias → confirmación → personas/roles/jerarquía/secciones`

## Capas

- **Territorio:** municipios, distritos locales, secciones electorales.
- **Personas:** identidad operativa y datos opcionales de domicilio.
- **Estructura:** estructura, membresías, superior directo y roles.
- **Territorialización:** persona_secciones.
- **Importación:** archivo, RAW, normalizado e incidencias.
- **Seguridad:** profiles, roles de aplicación, RLS y auditoría preparados.

## Reglas de datos

1. `VOCEROS` solo existe como encabezado fuente; en operación se interpreta como `PROMOVIDO`.
2. Un coordinador también puede tener rol `PROMOVIDO` si aparece como registro terminal.
3. No se fusionan automáticamente personas por teléfono con nombres distintos.
4. Una sección inexistente puede crearse como `PROVISIONAL` para permitir operación inmediata.
5. Un catálogo oficial posterior actualiza la misma clave de sección a `OFICIAL`.
6. Municipio fuera del catálogo de Sinaloa no se elimina: la persona se conserva y se genera incidencia, pero no se crea un vínculo territorial inválido.
7. Domicilio es opcional y no condiciona la importación.
