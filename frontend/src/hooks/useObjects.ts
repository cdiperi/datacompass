/**
 * TanStack Query hooks for catalog objects.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getObjects, getObject, updateObject } from '../api/client'
import type {
  CatalogObjectSummary,
  CatalogObjectDetail,
  ObjectFilters,
  ObjectUpdateRequest,
} from '../api/types'

export const objectKeys = {
  all: ['objects'] as const,
  lists: () => [...objectKeys.all, 'list'] as const,
  list: (filters: ObjectFilters) => [...objectKeys.lists(), filters] as const,
  details: () => [...objectKeys.all, 'detail'] as const,
  detail: (id: string | number) => [...objectKeys.details(), String(id)] as const,
}

export function useObjects(filters: ObjectFilters = {}) {
  return useQuery<CatalogObjectSummary[], Error>({
    queryKey: objectKeys.list(filters),
    queryFn: () => getObjects(filters),
  })
}

export function useObject(id: string | number) {
  return useQuery<CatalogObjectDetail, Error>({
    queryKey: objectKeys.detail(id),
    queryFn: () => getObject(id),
    enabled: !!id,
  })
}

export function useUpdateObject() {
  const queryClient = useQueryClient()

  return useMutation<
    CatalogObjectDetail,
    Error,
    { id: string | number; data: ObjectUpdateRequest }
  >({
    mutationFn: ({ id, data }) => updateObject(id, data),
    onSuccess: (updatedObject) => {
      // Update the specific object cache
      queryClient.setQueryData(objectKeys.detail(updatedObject.id), updatedObject)
      // Invalidate list queries to refresh
      queryClient.invalidateQueries({ queryKey: objectKeys.lists() })
    },
  })
}
