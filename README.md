# ICC Control Territorial V3.2

Plataforma Streamlit para análisis de estructura territorial, jerarquía por **Grupo 0**, cobertura seccional de Sinaloa, casillas y reportes ejecutivos.

## Operación V3.2

La versión incluye una **base operativa precargada de 12,211 registros**. Al iniciar la aplicación se carga automáticamente desde `data/base/icc_estructura_12211.csv.gz`; no es necesario volver a subir el Excel fuente para trabajar con este corte.

Flujo principal:

`Base precargada → Grupo 0 → estructura → sección → cartografía → casilla → mapa → reportes ejecutivos`

El importador de Excel se conserva como herramienta administrativa/futura, pero ya no es necesario para arrancar la base consolidada incluida en esta versión.

## Grupo 0

- `COORDINADOR` del archivo consolidado se interpreta como **Grupo 0**.
- Se conservan Grupo 1 a Grupo 7 para reconstrucción y trazabilidad de la jerarquía.
- Los reportes ejecutivos pueden filtrarse por Grupo 0 sin perder la posibilidad de analizar niveles subordinados.
- El sistema no recomienda ni asigna automáticamente qué Grupo 0 debe atender una zona sin presencia; únicamente identifica la brecha territorial.

## Reportes ejecutivos

`Reportes` incorpora filtros superiores por:

- Grupo 0;
- municipio;
- distrito local;
- distrito federal.

Incluye:

- resumen ejecutivo;
- ranking y detalle por Grupo 0;
- cobertura territorial por sección;
- secciones **CON PRESENCIA / SIN PRESENCIA**;
- cobertura por municipio, distrito local y distrito federal;
- reporte de casillas;
- promovidos con casilla exacta;
- promovidos pendientes de desglose individual.

Los paneles permiten descarga CSV y existe una **exportación ejecutiva a Excel** que respeta los filtros activos y genera varias hojas de trabajo.

## Secciones y promovidos

El Reporte de Secciones muestra el total real de registros de promovidos por sección y permite abrir el detalle individual con:

- promovido;
- teléfono disponible;
- Grupo 0;
- fila del Excel fuente;
- casilla exacta cuando exista;
- estado y criterio de asignación de casilla.

`VOCEROS` del archivo fuente se presenta operativamente como **PROMOVIDOS**, conservando el origen para trazabilidad.

## Casillas

V3.2 evita los **ceros falsos** y separa casilla EXACTA, SUGERIDA y PENDIENTE.

La asignación individual de casilla solo se considera exacta cuando existe una regla determinística, por ejemplo:

- casilla explícita válida;
- sección con una sola casilla;
- localidad extraordinaria con correspondencia única;
- rango alfabético oficial que produzca una única correspondencia.

Cuando una sección tiene Básica/Contiguas y no existe información suficiente para repartir individualmente a los promovidos, se mantiene el total real de la sección y el desglose se muestra como **PENDIENTE DE DESGLOSE INDIVIDUAL**; nunca se inventa una casilla ni se convierte esa ausencia de información en cero.

El sistema intenta activar automáticamente el catálogo histórico/oficial de casillas disponible mediante `core/historical_booths.py`. Si el catálogo no puede recuperarse, la aplicación continúa operando y lo informa expresamente.

## Mapa

El mapa seccional ocupa ahora prácticamente todo el ancho útil de Streamlit y utiliza una altura aproximada de **840 px**. Los filtros permanecen arriba y la ficha detallada se muestra debajo para evitar comprimir la cartografía.

## Cartografía

La cartografía seccional de Sinaloa está precargada. La sección funciona como llave para derivar, cuando exista correspondencia determinística:

- municipio;
- distrito local;
- distrito federal;
- tipo de sección.

Las secciones de la cartografía sin registros del filtro activo se identifican como **SIN PRESENCIA**.

## Despliegue en Streamlit Cloud

1. Sustituye el contenido del repositorio privado por esta versión.
2. Conserva tus Secrets de Supabase si ya están configurados.
3. Main file: `app.py`.
4. Haz Deploy/Reboot.
5. La base consolidada se carga automáticamente al iniciar.

No es necesario volver a subir el Excel de 12,211 registros para este corte.

## Supabase

V3.2 mantiene compatibilidad con la arquitectura V3. Si ya ejecutaste los esquemas anteriores, no es necesario borrar ni recrear la base para usar el modo local/precargado incluido en esta entrega.

## Identidad visual

Los reportes utilizan una paleta institucional guinda/tinto para gráficas, encabezados y elementos ejecutivos. El color principal de interfaz de esta versión es `#7A1732`, con fondos claros para conservar contraste y legibilidad.

## Versión

`3.2.0`

## Motor de casilla V3.2

La asignación individual usa tres estados:

- **EXACTA / AUTOMÁTICA:** casilla única, casilla explícita válida, localidad que determina una extraordinaria o rango alfabético oficial con apellido suficientemente confiable.
- **SUGERIDA:** cuando existen varias casillas B/C pero el catálogo no publica rangos de apellidos, se genera una proyección operativa estable por apellido. Si existe Lista Nominal por casilla, se usa como ponderador. La sugerencia queda marcada y no se presenta como dato oficial.
- **PENDIENTE:** se conserva cuando faltan catálogo, apellido utilizable, localidad para una extraordinaria o existe una contradicción/ambigüedad.

Los reportes y exportaciones muestran por separado exactas, sugeridas y pendientes.
