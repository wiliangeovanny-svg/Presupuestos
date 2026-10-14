-- ============================================================
-- MIGRACIÓN: Cronograma Valorado
-- Ejecutar en: Supabase > SQL Editor (proyectos que ya tenían el esquema base)
-- ============================================================

-- 1. Datos de planificación temporal en cada proyecto
alter table public.proyectos
    add column if not exists requiere_cronograma boolean not null default false,
    add column if not exists fecha_inicio date,
    add column if not exists unidad_periodo text not null default 'mes'
        check (unidad_periodo in ('semana', 'quincena', 'mes')),
    add column if not exists num_periodos integer not null default 12
        check (num_periodos > 0 and num_periodos <= 60);

-- 2. Rango de ejecución de cada ítem del presupuesto (para el reparto automático)
create table if not exists public.cronograma_items (
    id uuid primary key default gen_random_uuid(),
    presupuesto_item_id uuid not null unique references public.presupuesto_items(id) on delete cascade,
    periodo_inicio integer not null default 1,
    periodo_fin integer not null default 1,
    created_at timestamptz default now()
);

-- 3. Detalle: % de la cantidad total del rubro que se ejecuta en cada periodo
create table if not exists public.cronograma_detalle (
    id uuid primary key default gen_random_uuid(),
    cronograma_item_id uuid not null references public.cronograma_items(id) on delete cascade,
    periodo integer not null,
    porcentaje numeric(6,3) not null default 0,
    unique (cronograma_item_id, periodo)
);

-- ============================================================
-- RLS: la visibilidad se hereda del proyecto, igual que presupuesto_items
-- ============================================================
alter table public.cronograma_items enable row level security;
alter table public.cronograma_detalle enable row level security;

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
