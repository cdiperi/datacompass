/**
 * TanStack Query hooks for lineage data.
 */

import { useQuery } from '@tanstack/react-query'
import { getLineage, getLineageSummary } from '../api/client'
import type { LineageFilters, LineageGraph, LineageSummary } from '../api/types'

export const lineageKeys = {
  all: ['lineage'] as const,
  graph: (id: string | number, filters: LineageFilters) =>
    [...lineageKeys.all, 'graph', String(id), filters] as const,
  summary: (id: string | number) =>
    [...lineageKeys.all, 'summary', String(id)] as const,
}

/**
 * Fetch lineage graph for an object.
 */
export function useLineage(
  objectId: string | number,
  filters: LineageFilters = {}
) {
  return useQuery<LineageGraph, Error>({
    queryKey: lineageKeys.graph(objectId, filters),
    queryFn: () => getLineage(objectId, filters),
    enabled: !!objectId,
  })
}

/**
 * Fetch lineage summary counts for an object.
 */
export function useLineageSummary(objectId: string | number) {
  return useQuery<LineageSummary, Error>({
    queryKey: lineageKeys.summary(objectId),
    queryFn: () => getLineageSummary(objectId),
    enabled: !!objectId,
  })
}
