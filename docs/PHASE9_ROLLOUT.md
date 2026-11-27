# Phase 9 rollout readiness

Phase 9 adds Hindi/English storefront copy and a lightweight assigned-driver workflow. It can be rolled out independently of the Phase 7/8 production acceptance items; those items remain open and must not be treated as completed by this rollout.

## Before deployment

- Keep `PHONE_OTP_ENABLED=false`. Phase 9 does not require an SMS provider, DLT registration, or OTP credentials.
- Confirm the deployment has the API and web bundles from the same revision. The generated API client schema is checked into `packages/api-client`.
- Back up the database and review migration `0012_delivery_workflow` before applying it. It adds nullable order assignment and delivery timestamps, an optional store default-driver setting, role-check triggers, and an assigned-only delivery RLS policy. This migration is additive; do not manually drop or rewrite existing order data.
- Verify the service-role API connection used by FastAPI and RLS policies in the target environment. Browser clients must not receive service-role credentials.
- Confirm at least one active delivery-role profile exists. If desired, choose a default driver in admin settings; assignment remains optional and admins can override it per order.

## Apply and verify

1. Run the normal Alembic upgrade for the API deployment, including `0012_delivery_workflow`.
2. Verify schema presence for `orders.assigned_to`, `orders.out_for_delivery_at`, `orders.delivered_at`, and `store_settings.default_delivery_profile_id`.
3. In an authenticated admin session, assign an order and verify the assigned driver can see it in the mobile delivery view.
4. Verify a different delivery profile cannot list, read, or transition that order. Check API authorization and database RLS using the deployment's normal integration-test credentials.
5. Test `shipped → out_for_delivery → delivered`, repeat each same-target request to verify idempotent retry behavior, and verify an unassigned order or backward transition is rejected.
6. Switch English/Hindi, reload, and verify the saved selection and translated customer navigation, catalogue, cart, checkout, and order tracking. Confirm focus, accessible names, and mobile layouts remain usable.
7. Confirm admin assignment/default-driver controls work and that customer cart controls are not shown in admin surfaces.

## Automated checks

From the repository root:

```sh
npm run typecheck
npm run lint
npm test
```

API tests:

```sh
cd apps/api
pytest
```

Delivery integration tests require `TEST_DATABASE_URL`; without it, the test module skips database-backed policy, migration, and transition verification. Do not report database/RLS acceptance based only on a skipped test run.

## Rollback and operational limits

- Roll back the application revision first if needed. The migration is additive and leaves existing orders valid, but do not downgrade/drop its columns while a deployed application may still reference them.
- Driver access is limited to assigned active orders; the workflow does not provide driver self-assignment, route optimization, or SMS notifications.
- Keep the Phase 7/8 PWA, push, origin/CORS, provider-delivery, and public-site acceptance checks tracked separately.
