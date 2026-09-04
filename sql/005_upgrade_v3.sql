-- ICC CONTROL TERRITORIAL V3.0
-- Esta versión no requiere cambios destructivos sobre el esquema V2.
-- Las mejoras V3 se concentran en interfaz, trazabilidad del modo temporal,
-- inferencia de apellidos dentro del normalized_data JSON y motor de casillas.
--
-- Si vienes de V2.x y ya ejecutaste 001_schema.sql + 004_upgrade_v2.sql,
-- NO es necesario recrear la base.
-- Este archivo se conserva como checkpoint de versión para despliegues.

select 'ICC Control Territorial V3: esquema compatible con V2' as status;
