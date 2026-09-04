-- ICC Control Territorial V2.0
-- Enriquecimiento territorial, distrito federal y metadatos de catálogo de casillas.
-- Idempotente: puede ejecutarse sobre V1.x.

create table if not exists public.distritos_federales (
    id bigserial primary key,
    numero smallint not null unique,
    nombre text,
    activo boolean not null default true,
    created_at timestamptz not null default now()
);
insert into public.distritos_federales(numero,nombre)
select n, 'Distrito Federal ' || lpad(n::text,2,'0')
from generate_series(1,7) n
on conflict (numero) do update set activo=true;

alter table public.secciones_electorales add column if not exists distrito_federal_id bigint references public.distritos_federales(id);
alter table public.secciones_electorales add column if not exists tipo_seccion varchar(20);
alter table public.secciones_electorales add column if not exists fuente_territorial text;
alter table public.secciones_electorales add column if not exists municipio_clave_cartografia smallint;
create index if not exists idx_secciones_distrito_federal on public.secciones_electorales(distrito_federal_id);

alter table public.casillas_electorales add column if not exists proceso_electoral text;
alter table public.casillas_electorales add column if not exists estatus_catalogo varchar(30) default 'OPERATIVO_POR_VALIDAR';
alter table public.casillas_electorales add column if not exists distrito_local smallint;
alter table public.casillas_electorales add column if not exists distrito_federal smallint;
alter table public.casillas_electorales add column if not exists lista_nominal integer;
alter table public.casillas_electorales add column if not exists padron_electoral integer;

create table if not exists public.catalogos_casillas (
    id uuid primary key default gen_random_uuid(),
    proceso_electoral text not null,
    anio integer,
    fuente text,
    url_fuente text,
    estatus varchar(30) not null default 'HISTORICO_REFERENCIA',
    vigente boolean not null default false,
    total_registros integer,
    total_secciones integer,
    notas text,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
drop trigger if exists trg_catalogos_casillas_updated_at on public.catalogos_casillas;
create trigger trg_catalogos_casillas_updated_at before update on public.catalogos_casillas for each row execute function public.set_updated_at();

-- Vista seccional V2.
drop view if exists public.vw_secciones_resumen;
create view public.vw_secciones_resumen as
select
    s.id as seccion_id,
    s.numero,
    m.nombre as municipio,
    dl.numero as distrito_local,
    df.numero as distrito_federal,
    s.tipo_seccion,
    s.estado_catalogo,
    s.fuente_catalogo,
    s.fuente_territorial,
    s.vigencia,
    s.centroide_lat,
    s.centroide_lon,
    s.geometria_geojson,
    count(distinct ps.persona_id) filter (where ps.activo = true) as personas_registradas,
    count(distinct ps.persona_id) filter (
      where ps.activo = true and exists (
        select 1 from public.persona_roles_estructura pre
        join public.roles_estructura re on re.id = pre.rol_id
        where pre.persona_id = ps.persona_id and pre.activo = true and re.codigo = 'PROMOVIDO'
      )
    ) as promovidos,
    count(distinct ps.persona_id) filter (
      where ps.activo = true and exists (
        select 1 from public.persona_roles_estructura pre
        join public.roles_estructura re on re.id = pre.rol_id
        where pre.persona_id = ps.persona_id and pre.activo = true and re.codigo like 'COORDINADOR%'
      )
    ) as coordinadores
from public.secciones_electorales s
left join public.municipios m on m.id = s.municipio_id
left join public.distritos_locales dl on dl.id = s.distrito_local_id
left join public.distritos_federales df on df.id = s.distrito_federal_id
left join public.persona_secciones ps on ps.seccion_id = s.id and ps.activo = true
where s.activo = true
group by s.id,s.numero,m.nombre,dl.numero,df.numero,s.tipo_seccion,s.estado_catalogo,s.fuente_catalogo,s.fuente_territorial,s.vigencia,s.centroide_lat,s.centroide_lon,s.geometria_geojson;

-- Vista agregada de casillas V2.
drop view if exists public.vw_casillas_resumen;
create view public.vw_casillas_resumen as
select
  c.id as casilla_id,
  s.id as seccion_id,
  s.numero as seccion,
  m.nombre as municipio,
  dl.numero as distrito_local,
  df.numero as distrito_federal,
  c.clave_casilla,
  c.tipo_casilla,
  c.numero_casilla,
  c.proceso_electoral,
  c.estatus_catalogo,
  c.lista_nominal,
  c.domicilio,
  count(distinct pc.persona_id) filter (where pc.activo=true) as promovidos,
  count(distinct pc.coordinador_id) filter (where pc.activo=true and pc.coordinador_id is not null) as coordinadores_con_promovidos,
  topc.coordinador_mayor_estructura,
  topc.promovidos_coordinador_top,
  resp.responsable_formal
from public.casillas_electorales c
join public.secciones_electorales s on s.id=c.seccion_id
left join public.municipios m on m.id=s.municipio_id
left join public.distritos_locales dl on dl.id=s.distrito_local_id
left join public.distritos_federales df on df.id=s.distrito_federal_id
left join public.persona_casillas pc on pc.casilla_id=c.id and pc.activo=true
left join lateral (
  select p.nombre_completo as coordinador_mayor_estructura, count(*)::integer as promovidos_coordinador_top
  from public.persona_casillas pc2
  join public.personas p on p.id=pc2.coordinador_id
  where pc2.casilla_id=c.id and pc2.activo=true and pc2.coordinador_id is not null
  group by p.id,p.nombre_completo
  order by count(*) desc,p.nombre_completo
  limit 1
) topc on true
left join lateral (
  select p.nombre_completo as responsable_formal
  from public.responsabilidades_territoriales rt
  join public.personas p on p.id=rt.persona_id
  where rt.tipo_territorio='CASILLA' and rt.casilla_id=c.id and rt.activo=true and rt.es_principal=true
  order by rt.created_at desc limit 1
) resp on true
where c.activo=true
group by c.id,s.id,s.numero,m.nombre,dl.numero,df.numero,c.clave_casilla,c.tipo_casilla,c.numero_casilla,c.proceso_electoral,c.estatus_catalogo,c.lista_nominal,c.domicilio,
         topc.coordinador_mayor_estructura,topc.promovidos_coordinador_top,resp.responsable_formal;

alter table public.distritos_federales enable row level security;
alter table public.catalogos_casillas enable row level security;
