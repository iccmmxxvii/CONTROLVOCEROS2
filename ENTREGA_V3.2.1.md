# ICC Control Territorial V3.2.1 AUTOBASE

Esta entrega corrige el despliegue de la base precargada.

## Importante
Los archivos de este paquete deben quedar directamente en la raíz del repositorio:

- `app.py`
- `core/`
- `pages/`
- `data/`
- `requirements.txt`

No debe existir una carpeta adicional `randynuevo-main/` envolviendo el proyecto.

## Base precargada
El sistema espera automáticamente:

`data/base/icc_estructura_12211.csv.gz`

Contiene los 12,211 registros procesados. No es necesario utilizar **Cargar Excel** para esta base.

Si el archivo falta, el Dashboard mostrará un error explícito en vez de solicitar una importación manual.
