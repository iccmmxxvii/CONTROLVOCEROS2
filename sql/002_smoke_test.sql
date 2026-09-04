select 'municipios' as objeto, count(*) as registros from public.municipios
union all select 'distritos_locales', count(*) from public.distritos_locales
union all select 'roles_estructura', count(*) from public.roles_estructura
union all select 'casillas_electorales', count(*) from public.casillas_electorales
union all select 'responsabilidades_territoriales', count(*) from public.responsabilidades_territoriales;

select to_regclass('public.vw_personas_detalle') as vw_personas_detalle,
       to_regclass('public.vw_estructura_arbol') as vw_estructura_arbol,
       to_regclass('public.vw_secciones_resumen') as vw_secciones_resumen,
       to_regclass('public.vw_casillas_resumen') as vw_casillas_resumen;
