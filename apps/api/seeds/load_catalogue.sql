-- Load the seed catalogue into a hosted Supabase database without handing the
-- database password to a laptop (or to an agent sandbox).
--
-- How it works: `pg_net` fetches `catalogue.json` from this repository over HTTPS,
-- then a handful of `INSERT ... SELECT` statements upsert it. The data itself
-- never travels through a tool call, so prices and descriptions stay exactly as
-- reviewed in `catalogue.json`.
--
-- Prerequisites
--   * the repository is public (it is) and the file exists on the branch below;
--   * `pg_net` is available (it ships with Supabase).
--
-- Usage (Supabase SQL editor, or the connector's execute_query):
--   1. run STEP 1 and wait a second or two;
--   2. run STEP 2 until it reports the JSON size;
--   3. run STEP 3 (idempotent — safe to re-run after editing catalogue.json).
--
-- The API's own seeder (`python -m app.scripts.seed`) writes the same rows from
-- the same data; this script exists for hosted databases where only SQL is
-- available. Keep both in step by regenerating catalogue.json after edits:
--   cd apps/api && python -m app.scripts.seed --print-json > seeds/catalogue.json

-- ===========================================================================
-- STEP 1 — fetch the payload
-- ===========================================================================
create extension if not exists pg_net with schema extensions;

select extensions.net.http_get(
  'https://raw.githubusercontent.com/Jashan-ux/TripatGroceryStore/arena/660db374-tripatgrocerystore/apps/api/seeds/catalogue.json'
) as request_id;

-- STEP 2 — confirm the download (retry a moment later if this is empty)
-- select id, status_code, length(content::text) as bytes from net._http_response order by id desc limit 3;

-- ===========================================================================
-- STEP 3 — upsert the catalogue
-- ===========================================================================
begin;

create temporary view payload as
select content::jsonb as doc
from extensions._http_response
where status_code = 200
order by id desc
limit 1;

-- 3a. top-level categories
insert into public.categories (slug, name, emoji, sort_order, description, parent_id, is_active)
select c.slug, c.name, c.emoji, c.sort_order, c.description, null, true
from payload p,
     jsonb_to_recordset(p.doc -> 'categories')
       as c(slug text, name text, emoji text, sort_order int, description text, parent_slug text)
where c.parent_slug is null
on conflict (slug) do update
  set name = excluded.name, emoji = excluded.emoji, sort_order = excluded.sort_order,
      description = excluded.description, parent_id = null, is_active = true;

-- 3b. subcategories
insert into public.categories (slug, name, sort_order, description, parent_id, is_active)
select c.slug, c.name, c.sort_order, c.description,
       (select id from public.categories parent where parent.slug = c.parent_slug), true
from payload p,
     jsonb_to_recordset(p.doc -> 'categories')
       as c(slug text, name text, emoji text, sort_order int, description text, parent_slug text)
where c.parent_slug is not null
on conflict (slug) do update
  set name = excluded.name, sort_order = excluded.sort_order,
      description = excluded.description, parent_id = excluded.parent_id, is_active = true;

-- 3c. brands
insert into public.brands (slug, name, is_active)
select b.slug, b.name, true
from payload p,
     jsonb_to_recordset(p.doc -> 'brands') as b(slug text, name text)
on conflict (slug) do update set name = excluded.name, is_active = true;

-- 3d. products (tags arrive as JSON arrays and are cast once here)
insert into public.products (
  slug, name, description, brand_id, category_id, mrp_paise, price_paise,
  unit_label, stock, low_stock_threshold, images, tags, rating, is_active
)
select x.slug, x.name, x.description,
       (select id from public.brands brand where brand.slug = x.brand_slug),
       (select id from public.categories category where category.slug = x.category_slug),
       x.mrp_paise, x.price_paise, x.unit_label, x.stock, 10, '{}'::text[],
       coalesce((select array_agg(tag.value) from jsonb_array_elements_text(x.tags) as tag(value)),
                '{}'::text[]),
       x.rating, true
from payload p,
     jsonb_to_recordset(p.doc -> 'products') as x(
       slug text, name text, description text, brand_slug text, category_slug text,
       mrp_paise bigint, price_paise bigint, unit_label text, stock int,
       tags jsonb, rating numeric
     )
on conflict (slug) do update
  set name = excluded.name, description = excluded.description,
      brand_id = excluded.brand_id, category_id = excluded.category_id,
      mrp_paise = excluded.mrp_paise, price_paise = excluded.price_paise,
      unit_label = excluded.unit_label, stock = excluded.stock,
      tags = excluded.tags, rating = excluded.rating, is_active = true;

-- 3e. variants
insert into public.product_variants (
  product_id, label, mrp_paise, price_paise, stock, sort_order, is_active
)
select (select id from public.products product where product.slug = parent.slug),
       x.label, x.mrp_paise, x.price_paise, x.stock, x.sort_order, true
from payload p,
     jsonb_to_recordset(p.doc -> 'products') as parent(
       slug text, variants jsonb
     ),
     jsonb_to_recordset(parent.variants) as x(
       label text, mrp_paise bigint, price_paise bigint, stock int, sort_order int
     )
on conflict (product_id, label) do update
  set mrp_paise = excluded.mrp_paise, price_paise = excluded.price_paise,
      stock = excluded.stock, sort_order = excluded.sort_order, is_active = true;

commit;

-- STEP 4 — sanity check
-- select
--   (select count(*) from public.categories) as categories,
--   (select count(*) from public.brands)     as brands,
--   (select count(*) from public.products)   as products,
--   (select count(*) from public.product_variants) as variants;
