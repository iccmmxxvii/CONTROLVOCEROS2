# ICC Control Territorial V3.3.2

- Corrige `StreamlitPageNotFoundError` del Dashboard al retirar el enlace directo al módulo oculto Pendientes y conflictos.
- Mantiene ocultos del menú: Catálogos, Importaciones, Captura y edición, Casillas y responsables, Pendientes y conflictos.
- Refuerza la intensidad guinda del mapa para que las secciones con presencia sean claramente visibles aun con pocos promovidos.
- Aumenta el contraste del resaltado de la sección seleccionada.
- Añade indicador visual mientras se prepara la base precargada al iniciar una sesión fría.

# Changelog

## V3.3.1
- Reintegrada la base precargada completa de 12,211 registros desde el repositorio V3.2.1.
- Menú operativo simplificado: se ocultan Catálogos, Historial de importaciones, Pendientes y conflictos, Captura y edición y Casillas y responsables.
- Cargar Excel vuelve al menú como puerta operativa principal.
- Carga de Excel acelerada con `st.cache_data` por contenido del archivo.
- Se mantienen mapa V3.3 en guinda, detalle lateral y reportes descargables por tabla.

## V3.2.0

- Nuevo motor de casillas con estados **EXACTA/AUTOMÁTICA**, **SUGERIDA** y **PENDIENTE**.
- Uso de rango alfabético oficial cuando el catálogo lo contiene.
- Fallback de sugerencia operativa por apellido para casillas B/C sin rango publicado; pondera por Lista Nominal cuando está disponible.
- Las casillas extraordinarias sin localidad permanecen pendientes para evitar asignaciones engañosas.
- Reportes ejecutivos separan exactas, sugeridas y pendientes y exportan las tres categorías.
- Reporte de Secciones muestra casilla exacta, sugerida y pendiente por sección.
- Centro de Pendientes incorpora una pestaña específica de sugerencias revisables.
- Optimización del motor por índice de sección: prueba de estrés con 12,211 registros reducida a ~1.1 s para el cálculo de asignación con catálogo sintético de múltiples casillas.
- 20 pruebas automatizadas aprobadas.

## V3.1.0

### Base precargada y Grupo 0
- Se integra al repositorio la base consolidada de **12,211 registros** en formato comprimido.
- La aplicación carga automáticamente la base al iniciar; ya no es necesario volver a subir el Excel para este corte.
- `COORDINADOR` se utiliza como **Grupo 0** y se conservan Grupo 1 a Grupo 7 para reconstrucción jerárquica.
- Los registros se mantienen como universo operativo; los nombres únicos se calculan por separado para control de duplicidades.

### Rendimiento
- Se optimiza la construcción de personas, bosque jerárquico, secciones y detección de conflictos.
- La reconstrucción local de la base completa deja de realizar búsquedas repetitivas por fila y pasa a operaciones vectorizadas/indexadas.

### Reportes ejecutivos
- Reportes se reorganiza como módulo ejecutivo con filtros por **Grupo 0, municipio, distrito local y distrito federal**.
- Se agrega Resumen ejecutivo, Grupo 0, Cobertura territorial y Casillas.
- Se identifican claramente las secciones **CON PRESENCIA** y **SIN PRESENCIA**.
- Las brechas territoriales se reportan sin recomendar ni asignar qué Grupo 0 debe atenderlas.
- Se incorpora exportación completa a Excel con múltiples hojas y descargas CSV por panel, respetando los filtros activos.

### Casillas
- La asignación se recalcula automáticamente cuando existe catálogo disponible.
- Se conservan las reglas `AUTOMATICA`, `CONFIRMADA`, `SUGERIDA` y `PENDIENTE`.
- Se eliminan los **ceros falsos**: cuando una sección tiene varias casillas y no existe información suficiente para una asignación individual, el reporte conserva el total de promovidos de la sección y muestra **PENDIENTE DE DESGLOSE INDIVIDUAL**.
- El Reporte de Secciones permite ver qué promovidos tienen casilla exacta y cuáles continúan pendientes, con el criterio/motivo correspondiente.

### Mapa
- El mapa pasa a utilizar prácticamente todo el ancho de la página y una altura aproximada de **840 px**.
- La ficha de detalle se desplaza debajo del mapa para evitar comprimir la cartografía.

### Identidad visual
- Se homologa la paleta ejecutiva a guinda/tinto con color principal `#7A1732`.

## V3.0.0

### Operación y navegación
- Se retira del menú operativo **Captura y edición**; el flujo ordinario queda centrado en cargas Excel.
- Se retira del menú **Casillas y responsables**; su código y tablas se conservan para una etapa futura.
- El módulo **Secciones** se convierte en **Reporte de Secciones**, con enfoque ejecutivo y operativo.
- Todas las páginas mantienen `layout="wide"` y reducen márgenes para aprovechar el espacio de pantalla.

### Estructura
- La búsqueda superior sincroniza automáticamente **Trazar dependencia**.
- Si existe una única coincidencia, la cadena se muestra sin volver a buscar a la persona.
- La ficha incluye superior directo, nivel relativo, dependientes directos y red descendente total.

### Casillas V3
- Se infieren apellidos desde el nombre completo cuando el Excel no trae columnas separadas.
- La inferencia conserva `apellido_origen` y `apellido_confianza`.
- Asignación `AUTOMATICA`, `SUGERIDA` o `PENDIENTE` con motivos legibles.
- Se distingue catálogo sin rangos alfabéticos, rango ambiguo, sección sin catálogo, casilla explícita no coincidente y otros motivos.
- Al activar/actualizar catálogo de casillas se recalculan las asignaciones sin recargar personas.
- Nunca se inventa una casilla.

### Trazabilidad
- Cada carga temporal recibe `importacion_id`, `fecha_importacion`, `archivo_origen`, `estructura_origen` y `fila_excel`.
- Las incidencias cartográficas heredan el archivo/fila que las originó.
- Los conflictos entre varios archivos muestran archivos y filas involucradas.
- Pendientes y conflictos incorpora filtros por archivo, estructura, severidad y motivo.

### Reporte de Secciones
- Filtros compactos por municipio, distrito local, distrito federal, estado y sección.
- KPI de secciones, cobertura, promovidos, casillas y pendientes.
- Ranking visual de secciones con mayor estructura registrada.
- Tabla ejecutiva reducida y ficha detallada por sección.
- Desglose de promovidos por casilla cuando el catálogo está disponible.
- Campos técnicos quedan en detalle avanzado.

### Reportes
- Se elimina la pestaña redundante **Territorio**.
- **Distritos** incorpora KPI, ranking, barras de cobertura y tablas más legibles.
- **Coordinadores** conserva ranking y gráfica, con paleta guinda/tinto basada en el color institucional de MORENA (Pantone 1805; aproximación de pantalla #C0311A).
- **Casillas** queda como reporte ejecutivo: Casilla, Sección, Municipio, Distrito local, Distrito federal y Promovidos totales.
- Se eliminan IDs internos y desglose por roles del reporte ejecutivo de casillas.

### Mapa
- Se conserva el mapa poligonal estable de V2.1.6: secciones con información coloreadas, secciones vacías transparentes con contorno, hover con promovidos/casillas y ficha lateral.

### Compatibilidad
- V3 es compatible con el esquema Supabase V2. Si ya ejecutaste `004_upgrade_v2.sql`, no necesitas recrear la base.
- Se incluye `005_upgrade_v3.sql` como checkpoint no destructivo.