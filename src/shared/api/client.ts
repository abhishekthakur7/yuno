import createClient from 'openapi-fetch'

import type { paths } from './schema'

// OpenAPI paths already include the `/api/v1` base path (spec §5.1), so the
// client makes same-origin requests with no extra baseUrl prefix.
export const client = createClient<paths>()
