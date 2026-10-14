-- ============================================================
-- ESQUEMA DE BASE DE DATOS - Sistema de APUs y Presupuestos
-- Ejecutar en: Supabase > SQL Editor
-- ============================================================

-- 1. PERFILES DE USUARIO
-- Se sincroniza automáticamente con auth.users mediante un trigger.
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    nombre text,
    rol text not null default 'usuario' check (rol in ('admin', 'editor', 'usuario')),
    created_at timestamptz default now()
);

-- Trigger: cuando se registra un usuario nuevo en Supabase Auth,
-- se crea automáticamente su fila en profiles con rol 'usuario'.
create or replace function public.handle_new_user()
returns trigger as $$
begin
    insert into public.profiles (id, email, nombre, rol)
    values (new.id, new.email, coalesce(new.raw_user_meta_data->>'nombre', new.email), 'usuario');
    return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();


-- 2. INSUMOS (materiales, mano de obra, equipos)
create table if not exists public.insumos (
    id uuid primary key default gen_random_uuid(),
    tipo text not null check (tipo in ('material', 'mano_obra', 'equipo')),
    descripcion text not null,
    unidad text not null,
    precio numeric(12,4) not null default 0,
    created_by uuid references public.profiles(id),
    updated_at timestamptz default now()
);

-- 3. RUBROS (plantillas de APU, reutilizables entre proyectos)
create table if not exists public.rubros (
    id uuid primary key default gen_random_uuid(),
    codigo text,
    descripcion text not null,
    unidad text not null,
    indirectos_utilidad numeric(6,2) not null default 20, -- % por defecto
    created_by uuid references public.profiles(id),
    created_at timestamptz default now()
);

-- 4. COMPOSICIÓN DE CADA RUBRO (detalle del APU)
create table if not exists public.rubro_insumos (
    id uuid primary key default gen_random_uuid(),
    rubro_id uuid not null references public.rubros(id) on delete cascade,
    insumo_id uuid not null references public.insumos(id) on delete restrict,
    cantidad numeric(12,4) not null default 1,
    rendimiento numeric(12,4), -- horas por unidad; solo aplica a mano_obra y equipo
    created_at timestamptz default now()
);

-- 5. PROYECTOS
create table if not exists public.proyectos (
    id uuid primary key default gen_random_uuid(),
    nombre text not null,
    descripcion text,
    ubicacion text,
    owner_id uuid not null references public.profiles(id),
    requiere_cronograma boolean not null default false, -- el cronograma valorado es opcional por proyecto
    fecha_inicio date,
    unidad_periodo text not null default 'mes' check (unidad_periodo in ('semana', 'quincena', 'mes')),
    num_periodos integer not null default 12 check (num_periodos > 0 and num_periodos <= 60),
    created_at timestamptz default now()
);

-- 6. PRESUPUESTO (rubros + cantidades de obra dentro de un proyecto)
create table if not exists public.presupuesto_items (
    id uuid primary key default gen_random_uuid(),
    proyecto_id uuid not null references public.proyectos(id) on delete cascade,
    rubro_id uuid not null references public.rubros(id),
    cantidad numeric(12,4) not null default 0,
    created_at timestamptz default now()
);

-- 7. CRONOGRAMA VALORADO: rango de ejecución de cada ítem del presupuesto
create table if not exists public.cronograma_items (
    id uuid primary key default gen_random_uuid(),
    presupuesto_item_id uuid not null unique references public.presupuesto_items(id) on delete cascade,
    periodo_inicio integer not null default 1,
    periodo_fin integer not null default 1,
    created_at timestamptz default now()
);

-- 8. CRONOGRAMA VALORADO: % de la cantidad total del rubro ejecutado en cada periodo
create table if not exists public.cronograma_detalle (
    id uuid primary key default gen_random_uuid(),
    cronograma_item_id uuid not null references public.cronograma_items(id) on delete cascade,
    periodo integer not null,
    porcentaje numeric(6,3) not null default 0,
    unique (cronograma_item_id, periodo)
);


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
alter table public.profiles enable row level security;
alter table public.insumos enable row level security;
alter table public.rubros enable row level security;
alter table public.rubro_insumos enable row level security;
alter table public.proyectos enable row level security;
alter table public.presupuesto_items enable row level security;
alter table public.cronograma_items enable row level security;
alter table public.cronograma_detalle enable row level security;

-- Función auxiliar: ¿el usuario actual es admin?
create or replace function public.is_admin()
returns boolean as $$
    select exists (
        select 1 from public.profiles
        where id = auth.uid() and rol = 'admin'
    );
$$ language sql security definer stable;

-- Función auxiliar: ¿el usuario actual es admin O editor?
-- El editor es un respaldo del administrador: puede editar precios de insumos,
-- la biblioteca de rubros/APU, y ve los proyectos de todo el equipo, pero no
-- administra roles de otros usuarios (eso queda reservado solo a 'admin').
create or replace function public.is_staff()
returns boolean as $$
    select exists (
        select 1 from public.profiles
        where id = auth.uid() and rol in ('admin', 'editor')
    );
$$ language sql security definer stable;

-- PROFILES: cada quien ve su propio perfil; admin ve todos
create policy "profiles_select" on public.profiles
    for select using (id = auth.uid() or public.is_admin());
create policy "profiles_update_own" on public.profiles
    for update using (id = auth.uid());
create policy "profiles_admin_update" on public.profiles
    for update using (public.is_admin());

-- INSUMOS: todos los autenticados leen; admin y editor escriben
create policy "insumos_select" on public.insumos
    for select using (auth.role() = 'authenticated');
create policy "insumos_write" on public.insumos
    for insert with check (public.is_staff());
create policy "insumos_update" on public.insumos
    for update using (public.is_staff());
create policy "insumos_delete" on public.insumos
    for delete using (public.is_staff());

-- RUBROS: todos los autenticados leen; admin y editor escriben
create policy "rubros_select" on public.rubros
    for select using (auth.role() = 'authenticated');
create policy "rubros_write" on public.rubros
    for insert with check (public.is_staff());
create policy "rubros_update" on public.rubros
    for update using (public.is_staff());
create policy "rubros_delete" on public.rubros
    for delete using (public.is_staff());

-- RUBRO_INSUMOS: sigue las mismas reglas que rubros
create policy "rubro_insumos_select" on public.rubro_insumos
    for select using (auth.role() = 'authenticated');
create policy "rubro_insumos_write" on public.rubro_insumos
    for insert with check (public.is_staff());
create policy "rubro_insumos_update" on public.rubro_insumos
    for update using (public.is_staff());
create policy "rubro_insumos_delete" on public.rubro_insumos
    for delete using (public.is_staff());

-- PROYECTOS: cada quien ve/edita los suyos; admin y editor ven/editan todos
create policy "proyectos_select" on public.proyectos
    for select using (owner_id = auth.uid() or public.is_staff());
create policy "proyectos_insert" on public.proyectos
    for insert with check (owner_id = auth.uid());
create policy "proyectos_update" on public.proyectos
    for update using (owner_id = auth.uid() or public.is_staff());
create policy "proyectos_delete" on public.proyectos
    for delete using (owner_id = auth.uid() or public.is_staff());

-- PRESUPUESTO_ITEMS: visibilidad heredada del proyecto
create policy "presupuesto_select" on public.presupuesto_items
    for select using (
        exists (
            select 1 from public.proyectos p
            where p.id = proyecto_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "presupuesto_insert" on public.presupuesto_items
    for insert with check (
        exists (
            select 1 from public.proyectos p
            where p.id = proyecto_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "presupuesto_update" on public.presupuesto_items
    for update using (
        exists (
            select 1 from public.proyectos p
            where p.id = proyecto_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "presupuesto_delete" on public.presupuesto_items
    for delete using (
        exists (
            select 1 from public.proyectos p
            where p.id = proyecto_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );

-- CRONOGRAMA_ITEMS y CRONOGRAMA_DETALLE: visibilidad heredada del proyecto,
-- igual que presupuesto_items (vía join con presupuesto_items -> proyectos)
create policy "cronograma_items_select" on public.cronograma_items
    for select using (
        exists (
            select 1 from public.presupuesto_items pi
            join public.proyectos p on p.id = pi.proyecto_id
            where pi.id = presupuesto_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_items_insert" on public.cronograma_items
    for insert with check (
        exists (
            select 1 from public.presupuesto_items pi
            join public.proyectos p on p.id = pi.proyecto_id
            where pi.id = presupuesto_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_items_update" on public.cronograma_items
    for update using (
        exists (
            select 1 from public.presupuesto_items pi
            join public.proyectos p on p.id = pi.proyecto_id
            where pi.id = presupuesto_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_items_delete" on public.cronograma_items
    for delete using (
        exists (
            select 1 from public.presupuesto_items pi
            join public.proyectos p on p.id = pi.proyecto_id
            where pi.id = presupuesto_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );

create policy "cronograma_detalle_select" on public.cronograma_detalle
    for select using (
        exists (
            select 1 from public.cronograma_items ci
            join public.presupuesto_items pi on pi.id = ci.presupuesto_item_id
            join public.proyectos p on p.id = pi.proyecto_id
            where ci.id = cronograma_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_detalle_insert" on public.cronograma_detalle
    for insert with check (
        exists (
            select 1 from public.cronograma_items ci
            join public.presupuesto_items pi on pi.id = ci.presupuesto_item_id
            join public.proyectos p on p.id = pi.proyecto_id
            where ci.id = cronograma_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_detalle_update" on public.cronograma_detalle
    for update using (
        exists (
            select 1 from public.cronograma_items ci
            join public.presupuesto_items pi on pi.id = ci.presupuesto_item_id
            join public.proyectos p on p.id = pi.proyecto_id
            where ci.id = cronograma_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );
create policy "cronograma_detalle_delete" on public.cronograma_detalle
    for delete using (
        exists (
            select 1 from public.cronograma_items ci
            join public.presupuesto_items pi on pi.id = ci.presupuesto_item_id
            join public.proyectos p on p.id = pi.proyecto_id
            where ci.id = cronograma_item_id
            and (p.owner_id = auth.uid() or public.is_staff())
        )
    );

-- ============================================================
-- Nota: para convertir al primer usuario en admin, ejecutar manualmente:
-- update public.profiles set rol = 'admin' where email = 'tu_correo@ejemplo.com';
--
-- Para asignar el rol 'editor' (respaldo del admin, edita precios y ve todos
-- los proyectos, pero no administra roles de otros usuarios):
-- update public.profiles set rol = 'editor' where email = 'correo_editor@ejemplo.com';
-- ============================================================
