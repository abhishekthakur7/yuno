import createClient from 'openapi-fetch'

import type { paths } from './schema'

// OpenAPI paths already include the `/api/v1` base path (spec §5.1), so the
// client makes same-origin requests with no extra baseUrl prefix.
// Resolve fetch at request time so tests and platform adapters can replace the
// transport without rebuilding the schema-bound client.
export const client = createClient<paths>({
  baseUrl: typeof window === 'undefined' ? 'http://localhost' : window.location.origin,
  fetch: (...args) => globalThis.fetch(...args),
})
