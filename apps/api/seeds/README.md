# Seed data

`catalogue.json` is the reviewed, real catalogue for Tripat Pansari · MSG Store —
41 categories, 30 brands, 70 products and 44 weight variants. It is generated from
`app/scripts/seed_data.py`, which is the only place catalogue content is written.

## Regenerate

```bash
cd apps/api
python -m app.scripts.seed --print-json > seeds/catalogue.json   # JSON (hosted loader)
python -m app.scripts.seed --print-sql  > seeds/catalogue.sql    # readable SQL (review)
```

## Apply

| Target | Command |
| --- | --- |
| Local / CI / anywhere with a DB URL | `python -m app.scripts.seed` |
| Hosted Supabase, SQL only | run `load_catalogue.sql` in the SQL editor or the connector |
| Owner laptop | `python -m app.scripts.seed --with-users` (also creates staging logins) |

Both paths are idempotent: rows are keyed on `slug` (and `(product_id, label)` for
variants), so re-running updates prices and stock instead of duplicating them.
`seed.py` refuses to run with `ENVIRONMENT=production`.

`load_catalogue.sql` fetches this file over HTTPS with `pg_net` and upserts it, so
no database password is needed on the machine doing the seeding.
