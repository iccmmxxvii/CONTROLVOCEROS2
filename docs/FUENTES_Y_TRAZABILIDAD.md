# Fuentes y trazabilidad

## Cartografía seccional

Fuente de entrada de esta V2: archivo `25 SINALOA (1).zip` aportado para el proyecto.

Capa utilizada: `SECCION`.

Campos preservados/derivados para el sistema:

- entidad
- distrito federal
- distrito local
- municipio
- sección
- tipo de sección
- geometría

Transformación utilizada:

- CRS origen: WGS 84 / UTM zona 13N (EPSG:32613)
- CRS de aplicación: WGS 84 (EPSG:4326)

La plataforma no cambia silenciosamente el dato capturado en Excel: conserva su valor fuente y marca contradicciones.

## Casillas históricas

Fuente pública prevista para el bootstrap histórico de pruebas:

`https://www.ieesinaloa.mx/wp-content/uploads/Transparencia/Organizacion/2024/3-Padron-Electoral-y-Lista-Nominal-Casillas-Sinaloa-2024-IEES.xlsx`

Fuente alternativa:

`https://www.ieesinaloa.mx/wp-content/uploads/Transparencia/Organizacion/2024/Casillas-APROBADAS-PEL-Sinaloa-2024.xlsx`

Estatus dentro de ICC: `HISTORICO_REFERENCIA`.

Al publicarse el catálogo del proceso vigente debe cargarse como nuevo catálogo y marcarse el anterior como histórico.

## Regla de no invención

Un dato puede mostrarse como:

- CAPTURADO: vino del Excel.
- DERIVADO: se obtiene determinísticamente de la sección/cartografía/relación del sistema.
- CALCULADO: es una métrica agregada.
- PENDIENTE DE VALIDAR: falta evidencia suficiente.
- NO DISPONIBLE: la fuente actual no lo contiene.
