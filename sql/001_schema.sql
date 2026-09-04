-- ICC CONTROL TERRITORIAL — V2.0 ESQUEMA COMPLETO
-- Ejecutar completo únicamente en un proyecto Supabase nuevo.
-- Si ya tienes V1.3, usa sql/004_upgrade_v2.sql en lugar de recrear la base.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =========================================================
-- TERRITORIO
-- =========================================================
create table if not exists public.municipios (
    id bigserial primary key,
    clave varchar(10),
    nombre text not null,
    nombre_normalizado text not null,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    unique (nombre_normalizado)
);

insert into public.municipios(nombre, nombre_normalizado) values
('Ahome','AHOME'),
('Angostura','ANGOSTURA'),
('Badiraguato','BADIRAGUATO'),
('Choix','CHOIX'),
('Concordia','CONCORDIA'),
('Cosalá','COSALA'),
('Culiacán','CULIACAN'),
('El Fuerte','EL FUERTE'),
('Elota','ELOTA'),
('Escuinapa','ESCUINAPA'),
('Guasave','GUASAVE'),
('Mazatlán','MAZATLAN'),
('Mocorito','MOCORITO'),
('Navolato','NAVOLATO'),
('Rosario','ROSARIO'),
('Salvador Alvarado','SALVADOR ALVARADO'),
('San Ignacio','SAN IGNACIO'),
('Sinaloa','SINALOA'),
('Eldorado','ELDORADO'),
('Juan José Ríos','JUAN JOSE RIOS')
on conflict (nombre_normalizado) do update set nombre = excluded.nombre, activo = true;

create table if not exists public.distritos_locales (
    id bigserial primary key,
    numero smallint not null,
    nombre text,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    unique (numero)
);

insert into public.distritos_locales(numero, nombre)
select n, 'Distrito Local ' || lpad(n::text, 2, '0')
from generate_series(1,24) n
on conflict (numero) do nothing;

create table if not exists public.secciones_electorales (
    id bigserial primary key,
    entidad smallint not null default 25,
    numero integer not null,
    municipio_id bigint references public.municipios(id),
    distrito_local_id bigint references public.distritos_locales(id),
    fuente_catalogo text,
    vigencia text,
    estado_catalogo varchar(20) not null default 'PROVISIONAL',
    centroide_lat double precision,
    centroide_lon double precision,
    geometria_geojson jsonb,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (entidad, numero)
);

alter table public.secciones_electorales add column if not exists estado_catalogo varchar(20) not null default 'PROVISIONAL';
create index if not exists idx_secciones_municipio on public.secciones_electorales(municipio_id);
create index if not exists idx_secciones_distrito on public.secciones_electorales(distrito_local_id);
create index if not exists idx_secciones_estado_catalogo on public.secciones_electorales(estado_catalogo);

drop trigger if exists trg_secciones_updated_at on public.secciones_electorales;
create trigger trg_secciones_updated_at before update on public.secciones_electorales for each row execute function public.set_updated_at();

-- =========================================================
-- PERSONAS Y DATOS FUTUROS DE DOMICILIO
-- =========================================================
create table if not exists public.personas (
    id uuid primary key default gen_random_uuid(),
    nombre_completo text not null,
    nombre_normalizado text not null,
    telefono varchar(20),
    correo text,
    estado_validacion varchar(20) not null default 'VALIDADO',
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.personas add column if not exists estado_validacion varchar(20) not null default 'VALIDADO';
create index if not exists idx_personas_nombre_normalizado on public.personas(nombre_normalizado);
create index if not exists idx_personas_telefono on public.personas(telefono) where telefono is not null;
create index if not exists idx_personas_estado on public.personas(estado_validacion);

drop trigger if exists trg_personas_updated_at on public.personas;
create trigger trg_personas_updated_at before update on public.personas for each row execute function public.set_updated_at();

create table if not exists public.persona_domicilios (
    id uuid primary key default gen_random_uuid(),
    persona_id uuid not null references public.personas(id) on delete cascade,
    calle text,
    numero_exterior text,
    numero_interior text,
    colonia text,
    codigo_postal varchar(10),
    localidad text,
    municipio_id bigint references public.municipios(id),
    estado text default 'SINALOA',
    referencias text,
    latitud double precision,
    longitud double precision,
    es_principal boolean not null default true,
    activo boolean not null default true,
    source_import_id uuid,
    source_row_number integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.persona_domicilios add column if not exists source_import_id uuid;
alter table public.persona_domicilios add column if not exists source_row_number integer;
create unique index if not exists uq_domicilio_source on public.persona_domicilios(source_import_id, source_row_number) where source_import_id is not null and source_row_number is not null;

drop trigger if exists trg_domicilios_updated_at on public.persona_domicilios;
create trigger trg_domicilios_updated_at before update on public.persona_domicilios for each row execute function public.set_updated_at();

-- =========================================================
-- ROLES Y ESTRUCTURA JERÁRQUICA
-- =========================================================
create table if not exists public.roles_estructura (
    id smallserial primary key,
    codigo varchar(50) not null unique,
    nombre text not null,
    activo boolean not null default true
);

insert into public.roles_estructura(codigo, nombre) values
('COORDINADOR_ESTATAL', 'Coordinador estatal'),
('COORDINADOR_MUNICIPAL', 'Coordinador municipal'),
('COORDINADOR_DISTRITAL', 'Coordinador distrital'),
('COORDINADOR_SECCIONAL', 'Coordinador seccional'),
('COORDINADOR', 'Coordinador'),
('RESPONSABLE_SECCION', 'Responsable de sección'),
('PROMOTOR', 'Promotor'),
('PROMOVIDO', 'Promovido')
on conflict (codigo) do update set nombre = excluded.nombre, activo = true;

create table if not exists public.estructuras (
    id uuid primary key default gen_random_uuid(),
    nombre text not null,
    descripcion text,
    persona_raiz_id uuid references public.personas(id),
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists uq_estructuras_nombre_activa on public.estructuras(lower(nombre)) where activo = true;

drop trigger if exists trg_estructuras_updated_at on public.estructuras;
create trigger trg_estructuras_updated_at before update on public.estructuras for each row execute function public.set_updated_at();

-- Tabla de importaciones debe existir antes de FKs source_import_id.
create table if not exists public.importaciones_excel (
    id uuid primary key default gen_random_uuid(),
    filename text not null,
    file_sha256 char(64) not null,
    sheet_name text,
    source_type varchar(20) not null default 'EXCEL',
    total_rows integer not null default 0,
    status varchar(30) not null default 'STAGING',
    structure_name text,
    created_by uuid references auth.users(id),
    created_at timestamptz not null default now(),
    confirmed_at timestamptz
);

alter table public.importaciones_excel add column if not exists structure_name text;
create index if not exists idx_importaciones_sha on public.importaciones_excel(file_sha256);
create index if not exists idx_importaciones_status on public.importaciones_excel(status);

-- Agregar FK diferida de domicilios si no existía.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'persona_domicilios_source_import_id_fkey') then
    alter table public.persona_domicilios
      add constraint persona_domicilios_source_import_id_fkey foreign key (source_import_id) references public.importaciones_excel(id);
  end if;
end $$;

create table if not exists public.estructura_miembros (
    id uuid primary key default gen_random_uuid(),
    estructura_id uuid not null references public.estructuras(id) on delete cascade,
    persona_id uuid not null references public.personas(id),
    superior_directo_id uuid references public.personas(id),
    fecha_inicio date,
    fecha_fin date,
    activo boolean not null default true,
    source_import_id uuid references public.importaciones_excel(id),
    source_row_number integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (persona_id is distinct from superior_directo_id)
);

-- Compatibilidad con V0.1: rol_id puede existir, pero V1 usa persona_roles_estructura.
create unique index if not exists uq_estructura_miembro_activo on public.estructura_miembros(estructura_id, persona_id) where activo = true;
create index if not exists idx_estructura_superior on public.estructura_miembros(estructura_id, superior_directo_id) where activo = true;

drop trigger if exists trg_miembros_updated_at on public.estructura_miembros;
create trigger trg_miembros_updated_at before update on public.estructura_miembros for each row execute function public.set_updated_at();

create table if not exists public.persona_roles_estructura (
    id uuid primary key default gen_random_uuid(),
    estructura_id uuid not null references public.estructuras(id) on delete cascade,
    persona_id uuid not null references public.personas(id) on delete cascade,
    rol_id smallint not null references public.roles_estructura(id),
    activo boolean not null default true,
    source_import_id uuid references public.importaciones_excel(id),
    created_at timestamptz not null default now()
);
create unique index if not exists uq_persona_rol_estructura_activo on public.persona_roles_estructura(estructura_id, persona_id, rol_id) where activo = true;

create table if not exists public.persona_secciones (
    id uuid primary key default gen_random_uuid(),
    persona_id uuid not null references public.personas(id) on delete cascade,
    seccion_id bigint not null references public.secciones_electorales(id),
    tipo_vinculo varchar(30) not null default 'REGISTRO_TERRITORIAL',
    es_principal boolean not null default true,
    activo boolean not null default true,
    source_import_id uuid references public.importaciones_excel(id),
    source_row_number integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.persona_secciones add column if not exists source_row_number integer;
create unique index if not exists uq_persona_seccion_vinculo_activo on public.persona_secciones(persona_id, seccion_id, tipo_vinculo) where activo = true;
create index if not exists idx_persona_secciones_section on public.persona_secciones(seccion_id) where activo = true;

drop trigger if exists trg_persona_secciones_updated_at on public.persona_secciones;
create trigger trg_persona_secciones_updated_at before update on public.persona_secciones for each row execute function public.set_updated_at();

-- =========================================================
-- STAGING / TRAZABILIDAD DE EXCEL
-- =========================================================
create table if not exists public.importacion_registros_raw (
    id bigserial primary key,
    import_id uuid not null references public.importaciones_excel(id) on delete cascade,
    row_number integer not null,
    raw_data jsonb not null,
    status varchar(30) not null default 'RAW',
    created_at timestamptz not null default now(),
    unique (import_id, row_number)
);

create table if not exists public.importacion_registros_normalizados (
    id bigserial primary key,
    import_id uuid not null references public.importaciones_excel(id) on delete cascade,
    row_number integer not null,
    normalized_data jsonb not null,
    validation_status varchar(30) not null default 'LISTO',
    created_at timestamptz not null default now(),
    unique (import_id, row_number)
);

create table if not exists public.importacion_incidencias (
    id bigserial primary key,
    import_id uuid not null references public.importaciones_excel(id) on delete cascade,
    row_number integer,
    severity varchar(20) not null,
    incident_type varchar(60) not null,
    field_name text,
    original_value text,
    message text not null,
    resolved boolean not null default false,
    resolved_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_import_incidencias_import on public.importacion_incidencias(import_id);

-- =========================================================
-- USUARIOS / ROLES DE APLICACIÓN PREPARADOS PARA ETAPA DE ACCESO
-- =========================================================
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    nombre text,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.app_roles (
    id smallserial primary key,
    codigo varchar(40) unique not null,
    nombre text not null
);
insert into public.app_roles(codigo,nombre) values
('ADMIN','Administrador'),('CAPTURA','Captura'),('CONSULTA','Consulta')
on conflict (codigo) do nothing;

create table if not exists public.profile_roles (
    profile_id uuid not null references public.profiles(id) on delete cascade,
    role_id smallint not null references public.app_roles(id) on delete cascade,
    primary key(profile_id, role_id)
);

create table if not exists public.audit_log (
    id bigserial primary key,
    user_id uuid references auth.users(id),
    action varchar(30) not null,
    table_name text not null,
    record_id text,
    old_data jsonb,
    new_data jsonb,
    created_at timestamptz not null default now()
);

-- =========================================================
-- VISTAS OPERATIVAS
-- =========================================================
drop view if exists public.vw_estructura_arbol;
create view public.vw_estructura_arbol as
with recursive arbol as (
    select
        em.estructura_id,
        em.persona_id,
        em.superior_directo_id,
        0::integer as nivel,
        array[em.persona_id]::uuid[] as ruta,
        array[p.nombre_completo]::text[] as ruta_nombres
    from public.estructura_miembros em
    join public.estructuras e on e.id = em.estructura_id
    join public.personas p on p.id = em.persona_id
    where em.activo = true
      and (em.persona_id = e.persona_raiz_id or em.superior_directo_id is null)

    union all

    select
        hijo.estructura_id,
        hijo.persona_id,
        hijo.superior_directo_id,
        padre.nivel + 1,
        padre.ruta || hijo.persona_id,
        padre.ruta_nombres || p_hijo.nombre_completo
    from public.estructura_miembros hijo
    join arbol padre
      on padre.estructura_id = hijo.estructura_id
     and hijo.superior_directo_id = padre.persona_id
    join public.personas p_hijo on p_hijo.id = hijo.persona_id
    where hijo.activo = true
      and not (hijo.persona_id = any(padre.ruta))
)
select
    a.estructura_id,
    e.nombre as estructura_nombre,
    a.persona_id,
    a.superior_directo_id,
    a.nivel,
    a.ruta,
    a.ruta_nombres,
    p.nombre_completo,
    sup.nombre_completo as superior_directo_nombre,
    coalesce(roles.roles, '') as roles,
    coalesce(secs.secciones, '') as secciones
from arbol a
join public.estructuras e on e.id = a.estructura_id
join public.personas p on p.id = a.persona_id
left join public.personas sup on sup.id = a.superior_directo_id
left join lateral (
    select string_agg(distinct re.nombre, ', ' order by re.nombre) as roles
    from public.persona_roles_estructura pre
    join public.roles_estructura re on re.id = pre.rol_id
    where pre.estructura_id = a.estructura_id and pre.persona_id = a.persona_id and pre.activo = true
) roles on true
left join lateral (
    select string_agg(distinct s.numero::text, ', ' order by s.numero::text) as secciones
    from public.persona_secciones ps
    join public.secciones_electorales s on s.id = ps.seccion_id
    where ps.persona_id = a.persona_id and ps.activo = true
) secs on true;


drop view if exists public.vw_personas_detalle;
create view public.vw_personas_detalle as
select
    p.id as persona_id,
    p.nombre_completo,
    p.nombre_normalizado,
    p.telefono,
    p.correo,
    p.estado_validacion,
    p.activo,
    p.created_at,
    mem.estructura_id,
    mem.estructura_nombre,
    mem.superior_directo_id,
    mem.superior_directo_nombre,
    coalesce(roles.roles, '') as roles,
    sec.numero as seccion,
    sec.municipio,
    sec.distrito_local
from public.personas p
left join lateral (
    select em.estructura_id, e.nombre as estructura_nombre, em.superior_directo_id, sup.nombre_completo as superior_directo_nombre
    from public.estructura_miembros em
    join public.estructuras e on e.id = em.estructura_id
    left join public.personas sup on sup.id = em.superior_directo_id
    where em.persona_id = p.id and em.activo = true
    order by em.created_at
    limit 1
) mem on true
left join lateral (
    select string_agg(distinct re.nombre, ', ' order by re.nombre) as roles
    from public.persona_roles_estructura pre
    join public.roles_estructura re on re.id = pre.rol_id
    where pre.persona_id = p.id and pre.activo = true
) roles on true
left join lateral (
    select s.numero, m.nombre as municipio, dl.numero as distrito_local
    from public.persona_secciones ps
    join public.secciones_electorales s on s.id = ps.seccion_id
    left join public.municipios m on m.id = s.municipio_id
    left join public.distritos_locales dl on dl.id = s.distrito_local_id
    where ps.persona_id = p.id and ps.activo = true
    order by ps.es_principal desc, ps.created_at desc
    limit 1
) sec on true
where p.activo = true;


drop view if exists public.vw_secciones_resumen;
create view public.vw_secciones_resumen as
select
    s.id as seccion_id,
    s.numero,
    m.nombre as municipio,
    dl.numero as distrito_local,
    s.estado_catalogo,
    s.fuente_catalogo,
    s.vigencia,
    s.centroide_lat,
    s.centroide_lon,
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
left join public.persona_secciones ps on ps.seccion_id = s.id and ps.activo = true
where s.activo = true
group by s.id, s.numero, m.nombre, dl.numero, s.estado_catalogo, s.fuente_catalogo, s.vigencia, s.centroide_lat, s.centroide_lon;

-- =========================================================
-- RLS
-- La V1 de Streamlit usa SERVICE_ROLE_KEY del lado servidor.
-- RLS queda habilitado para que la futura autenticación no requiera rediseñar la base.
-- =========================================================
alter table public.municipios enable row level security;
alter table public.distritos_locales enable row level security;
alter table public.secciones_electorales enable row level security;
alter table public.personas enable row level security;
alter table public.persona_domicilios enable row level security;
alter table public.roles_estructura enable row level security;
alter table public.estructuras enable row level security;
alter table public.estructura_miembros enable row level security;
alter table public.persona_roles_estructura enable row level security;
alter table public.persona_secciones enable row level security;
alter table public.importaciones_excel enable row level security;
alter table public.importacion_registros_raw enable row level security;
alter table public.importacion_registros_normalizados enable row level security;
alter table public.importacion_incidencias enable row level security;
alter table public.profiles enable row level security;
alter table public.app_roles enable row level security;
alter table public.profile_roles enable row level security;
alter table public.audit_log enable row level security;
-- ICC Control Territorial V1.3
-- Casillas, asignaciones y responsabilidades territoriales.

create table if not exists public.casillas_electorales (
    id uuid primary key default gen_random_uuid(),
    seccion_id bigint not null references public.secciones_electorales(id) on delete cascade,
    tipo_casilla varchar(12) not null,
    numero_casilla integer,
    clave_casilla text not null,
    apellido_desde text,
    apellido_hasta text,
    localidad text,
    domicilio text,
    fuente_catalogo text,
    vigencia text,
    activo boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists uq_casilla_clave_activa on public.casillas_electorales(seccion_id, upper(clave_casilla)) where activo=true;
create index if not exists idx_casillas_seccion on public.casillas_electorales(seccion_id) where activo=true;

drop trigger if exists trg_casillas_updated_at on public.casillas_electorales;
create trigger trg_casillas_updated_at before update on public.casillas_electorales for each row execute function public.set_updated_at();

create table if not exists public.persona_casillas (
    id uuid primary key default gen_random_uuid(),
    persona_id uuid not null references public.personas(id) on delete cascade,
    casilla_id uuid not null references public.casillas_electorales(id) on delete cascade,
    coordinador_id uuid references public.personas(id),
    estado_asignacion varchar(30) not null default 'PENDIENTE',
    criterio_asignacion text,
    activo boolean not null default true,
    source_import_id uuid references public.importaciones_excel(id),
    source_row_number integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists uq_persona_casilla_activa on public.persona_casillas(persona_id, casilla_id) where activo=true;
create index if not exists idx_persona_casilla_casilla on public.persona_casillas(casilla_id) where activo=true;
create index if not exists idx_persona_casilla_coord on public.persona_casillas(coordinador_id) where activo=true;

drop trigger if exists trg_persona_casillas_updated_at on public.persona_casillas;
create trigger trg_persona_casillas_updated_at before update on public.persona_casillas for each row execute function public.set_updated_at();

create table if not exists public.responsabilidades_territoriales (
    id uuid primary key default gen_random_uuid(),
    persona_id uuid not null references public.personas(id),
    tipo_territorio varchar(20) not null check (tipo_territorio in ('SECCION','CASILLA')),
    seccion_id bigint references public.secciones_electorales(id),
    casilla_id uuid references public.casillas_electorales(id),
    fecha_inicio date not null default current_date,
    fecha_fin date,
    es_principal boolean not null default true,
    activo boolean not null default true,
    asignado_por uuid references auth.users(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
      (tipo_territorio='SECCION' and seccion_id is not null and casilla_id is null)
      or
      (tipo_territorio='CASILLA' and casilla_id is not null)
    )
);
create unique index if not exists uq_resp_seccion_principal on public.responsabilidades_territoriales(seccion_id) where activo=true and es_principal=true and tipo_territorio='SECCION';
create unique index if not exists uq_resp_casilla_principal on public.responsabilidades_territoriales(casilla_id) where activo=true and es_principal=true and tipo_territorio='CASILLA';

drop trigger if exists trg_resp_territorial_updated_at on public.responsabilidades_territoriales;
create trigger trg_resp_territorial_updated_at before update on public.responsabilidades_territoriales for each row execute function public.set_updated_at();

-- Vista agregada de casillas.
drop view if exists public.vw_casillas_resumen;
create view public.vw_casillas_resumen as
select
  c.id as casilla_id,
  s.id as seccion_id,
  s.numero as seccion,
  m.nombre as municipio,
  c.clave_casilla,
  c.tipo_casilla,
  c.numero_casilla,
  c.domicilio,
  count(distinct pc.persona_id) filter (where pc.activo=true) as promovidos,
  count(distinct pc.coordinador_id) filter (where pc.activo=true and pc.coordinador_id is not null) as coordinadores_con_promovidos,
  topc.coordinador_mayor_estructura,
  topc.promovidos_coordinador_top,
  resp.responsable_formal
from public.casillas_electorales c
join public.secciones_electorales s on s.id=c.seccion_id
left join public.municipios m on m.id=s.municipio_id
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
group by c.id,s.id,s.numero,m.nombre,c.clave_casilla,c.tipo_casilla,c.numero_casilla,c.domicilio,
         topc.coordinador_mayor_estructura,topc.promovidos_coordinador_top,resp.responsable_formal;

alter table public.casillas_electorales enable row level security;
alter table public.persona_casillas enable row level security;
alter table public.responsabilidades_territoriales enable row level security;
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
