/**
 * TanStack Query hooks for data sources.
 */

import { useQuery } from '@tanstack/react-query'
import { getSources, getSource } from '../api/client'
import type { DataSource } from '../api/types'

export const sourceKeys = {
  all: ['sources'] as const,
  lists: () => [...sourceKeys.all, 'list'] as const,
  list: (activeOnly: boolean) => [...sourceKeys.lists(), { activeOnly }] as const,
  details: () => [...sourceKeys.all, 'detail'] as const,
  detail: (name: string) => [...sourceKeys.details(), name] as const,
}

export function useSources(activeOnly = false) {
  return useQuery<DataSource[], Error>({
    queryKey: sourceKeys.list(activeOnly),
    queryFn: () => getSources(activeOnly),
  })
}

export function useSource(name: string) {
  return useQuery<DataSource, Error>({
    queryKey: sourceKeys.detail(name),
    queryFn: () => getSource(name),
    enabled: !!name,
  })
}
