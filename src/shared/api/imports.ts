import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type ImportRecord = components['schemas']['ImportRecordResponse']
export type ImportStatement = components['schemas']['ImportStatementResponse']
export type ImportCreate = components['schemas']['ImportCreateRequest']
export type ImportCorrection = components['schemas']['ImportStatementPatchRequest']
export type ImportMapping = components['schemas']['ImportStatementMapRequest']
export type JobRef = components['schemas']['JobRefResponse']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, message: string): never {
  throw new ApiError(error?.message ?? message, status)
}

export function importsQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['imports', { goalId }],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/imports', {
        params: { query: { goal_id: goalId } },
      })
      if (error || !data) failure(error, response.status, 'Imports could not be loaded.')
      return data
    },
  })
}

export function importQueryOptions(importId: string | null) {
  return queryOptions({
    queryKey: ['imports', importId],
    enabled: Boolean(importId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/imports/{import_id}', { params: { path: { import_id: importId! } } })
      if (error || !data) failure(error, response.status, 'The import could not be loaded.')
      return data
    },
  })
}

export function importStatementsQueryOptions(importId: string | null) {
  return queryOptions({
    queryKey: ['imports', importId, 'statements'],
    enabled: Boolean(importId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/imports/{import_id}/statements', { params: { path: { import_id: importId! } } })
      if (error || !data) failure(error, response.status, 'Import statements could not be loaded.')
      return data
    },
  })
}

export async function createImport(body: ImportCreate) {
  const { data, error, response } = await client.POST('/api/v1/imports', { params: { header: { 'Idempotency-Key': crypto.randomUUID() } }, body })
  if (error || !data) failure(error, response.status, 'The original import could not be saved.')
  return data
}

async function enqueue(path: 'parse' | 'reprocess', importId: string) {
  const params = { path: { import_id: importId }, header: { 'Idempotency-Key': crypto.randomUUID() } }
  const result = path === 'parse'
    ? await client.POST('/api/v1/imports/{import_id}/parse', { params })
    : await client.POST('/api/v1/imports/{import_id}/reprocess', { params })
  if (result.error || !result.data) failure(result.error, result.response.status, `The ${path} job could not be queued.`)
  return result.data
}

export const parseImport = (importId: string) => enqueue('parse', importId)
export const reprocessImport = (importId: string) => enqueue('reprocess', importId)

export async function correctImportStatement(statement: ImportStatement, body: ImportCorrection) {
  const { data, error, response } = await client.PATCH('/api/v1/import-statements/{statement_id}', {
    params: { path: { statement_id: statement.id }, header: { 'If-Match': String(statement.row_version), 'Idempotency-Key': crypto.randomUUID() } },
    body,
  })
  if (error || !data) failure(error, response.status, 'The correction could not be saved.')
  return data
}

export async function mapImportStatement(statement: ImportStatement, body: ImportMapping) {
  const { data, error, response } = await client.POST('/api/v1/import-statements/{statement_id}/map', {
    params: { path: { statement_id: statement.id }, header: { 'If-Match': String(statement.row_version), 'Idempotency-Key': crypto.randomUUID() } }, body,
  })
  if (error || !data) failure(error, response.status, 'The topic mapping could not be saved.')
  return data
}

async function decide(statement: ImportStatement, decision: 'verify' | 'dismiss') {
  const params = { path: { statement_id: statement.id }, header: { 'If-Match': String(statement.row_version), 'Idempotency-Key': crypto.randomUUID() } }
  const result = decision === 'verify'
    ? await client.POST('/api/v1/import-statements/{statement_id}/verify', { params })
    : await client.POST('/api/v1/import-statements/{statement_id}/dismiss', { params })
  if (result.error || !result.data) failure(result.error, result.response.status, `The ${decision} decision could not be saved.`)
  return result.data
}

export const verifyImportStatement = (statement: ImportStatement) => decide(statement, 'verify')
export const dismissImportStatement = (statement: ImportStatement) => decide(statement, 'dismiss')
