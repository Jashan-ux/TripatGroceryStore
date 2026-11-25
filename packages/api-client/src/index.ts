/**
 * Typed access to the Tripat Pansari API surface.
 *
 * Everything here is derived from `../generated/schema.d.ts`, which is produced
 * from the FastAPI OpenAPI document. Never hand-write an API type: regenerate
 * with `npm run api:types`.
 */
import type { components, paths } from '../generated/schema';

export type ApiPaths = paths;
export type Schemas = components['schemas'];

/** Every operation, keyed by path then method. */
export type ApiOperation<P extends keyof paths, M extends keyof paths[P]> = paths[P][M];

/** Body type for a given operation (unwrapped from requestBody). */
export type ApiBody<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  requestBody: { content: { 'application/json': infer B } };
}
  ? B
  : never;

/** Success response type for a given operation. */
export type ApiResponse<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  responses: { 200: { content: { 'application/json': infer R } } };
}
  ? R
  : never;

// Named schema aliases for ergonomic use in components.
export type HealthResponse = Schemas['HealthResponse'];
export type HealthComponent = Schemas['HealthComponent'];
export type PublicConfig = Schemas['PublicConfig'];
export type StatusResponse = Schemas['StatusResponse'];
export type ErrorResponse = Schemas['ErrorResponse'];
export type ErrorDetail = Schemas['ErrorDetail'];

// Every other component schema is aliased automatically at generation time.
export * from '../generated/aliases';

export type { components, paths };
