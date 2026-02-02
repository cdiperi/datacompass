/**
 * TanStack Query hooks for search functionality.
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { search } from '../api/client'
import type { SearchResult, SearchFilters } from '../api/types'

export const searchKeys = {
  all: ['search'] as const,
  queries: () => [...searchKeys.all, 'query'] as const,
  query: (filters: SearchFilters) => [...searchKeys.queries(), filters] as const,
}

export function useSearch(filters: SearchFilters) {
  return useQuery<SearchResult[], Error>({
    queryKey: searchKeys.query(filters),
    queryFn: () => search(filters),
    enabled: filters.q.length > 0,
    placeholderData: keepPreviousData,
  })
}

/**
 * Hook that debounces search input to avoid excessive API calls.
 */
export function useDebouncedSearch(
  query: string,
  options: Omit<SearchFilters, 'q'> = {},
  debounceMs = 300
) {
  const [debouncedQuery, setDebouncedQuery] = useState(query)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, debounceMs)

    return () => clearTimeout(timer)
  }, [query, debounceMs])

  return useSearch({
    q: debouncedQuery,
    ...options,
  })
}
