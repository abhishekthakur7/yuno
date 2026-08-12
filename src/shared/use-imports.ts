import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  correctImportStatement,
  createImport,
  dismissImportStatement,
  importQueryOptions,
  importsQueryOptions,
  importStatementsQueryOptions,
  mapImportStatement,
  parseImport,
  reprocessImport,
  verifyImportStatement,
  type ImportCorrection,
  type ImportCreate,
  type ImportMapping,
  type ImportStatement,
} from './api/imports'

export function useImports(goalId: string | null, selectedImportId: string | null) {
  const queryClient = useQueryClient()
  const imports = useQuery(importsQueryOptions(goalId))
  const selectedImport = useQuery(importQueryOptions(selectedImportId))
  const statements = useQuery(importStatementsQueryOptions(selectedImportId))
  const refreshSelected = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['imports', { goalId }] }),
      queryClient.invalidateQueries({ queryKey: ['imports', selectedImportId] }),
    ])
  }
  const refreshStatements = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['imports', selectedImportId] }),
      queryClient.invalidateQueries({ queryKey: ['imports', selectedImportId, 'statements'] }),
      queryClient.invalidateQueries({ queryKey: ['imports', { goalId }] }),
    ])
  }
  const create = useMutation({ mutationFn: (body: ImportCreate) => createImport(body), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['imports', { goalId }] }) })
  const parse = useMutation({ mutationFn: (id: string) => parseImport(id), onSuccess: refreshSelected })
  const reprocess = useMutation({ mutationFn: (id: string) => reprocessImport(id), onSuccess: refreshSelected })
  const correct = useMutation({ mutationFn: ({ statement, body }: { statement: ImportStatement; body: ImportCorrection }) => correctImportStatement(statement, body), onSuccess: refreshStatements })
  const map = useMutation({ mutationFn: ({ statement, body }: { statement: ImportStatement; body: ImportMapping }) => mapImportStatement(statement, body), onSuccess: refreshStatements })
  const verify = useMutation({ mutationFn: verifyImportStatement, onSuccess: refreshStatements })
  const dismiss = useMutation({ mutationFn: dismissImportStatement, onSuccess: refreshStatements })
  return { imports, selectedImport, statements, create, parse, reprocess, correct, map, verify, dismiss, refreshSelected }
}
