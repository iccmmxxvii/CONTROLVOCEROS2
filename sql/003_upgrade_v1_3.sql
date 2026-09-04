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
