/**
 * TanStack Query hooks for Data Quality data.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getDQBreaches,
  getDQBreach,
  getDQConfigs,
  getDQConfig,
  getDQHubSummary,
  runDQConfig,
  updateDQBreachStatus,
} from '../api/client'
import type {
  BreachStatusUpdate,
  DQBreach,
  DQBreachFilters,
  DQConfigDetail,
  DQConfigFilters,
  DQConfigListItem,
  DQHubSummary,
  DQRunResult,
} from '../api/types'

export const dqKeys = {
  all: ['dq'] as const,
  configs: () => [...dqKeys.all, 'configs'] as const,
  configList: (filters: DQConfigFilters) =>
    [...dqKeys.configs(), 'list', filters] as const,
  configDetail: (id: number) => [...dqKeys.configs(), 'detail', id] as const,
  breaches: () => [...dqKeys.all, 'breaches'] as const,
  breachList: (filters: DQBreachFilters) =>
    [...dqKeys.breaches(), 'list', filters] as const,
  breachDetail: (id: number) => [...dqKeys.breaches(), 'detail', id] as const,
  hubSummary: () => [...dqKeys.all, 'hub', 'summary'] as const,
}

/**
 * Fetch DQ configs list.
 */
export function useDQConfigs(filters: DQConfigFilters = {}) {
  return useQuery<DQConfigListItem[], Error>({
    queryKey: dqKeys.configList(filters),
    queryFn: () => getDQConfigs(filters),
  })
}

/**
 * Fetch single DQ config with expectations.
 */
export function useDQConfig(configId: number) {
  return useQuery<DQConfigDetail, Error>({
    queryKey: dqKeys.configDetail(configId),
    queryFn: () => getDQConfig(configId),
    enabled: !!configId,
  })
}

/**
 * Fetch DQ breaches list.
 */
export function useDQBreaches(filters: DQBreachFilters = {}) {
  return useQuery<DQBreach[], Error>({
    queryKey: dqKeys.breachList(filters),
    queryFn: () => getDQBreaches(filters),
  })
}

/**
 * Fetch single DQ breach.
 */
export function useDQBreach(breachId: number) {
  return useQuery<DQBreach, Error>({
    queryKey: dqKeys.breachDetail(breachId),
    queryFn: () => getDQBreach(breachId),
    enabled: !!breachId,
  })
}

/**
 * Fetch DQ hub summary.
 */
export function useDQHubSummary() {
  return useQuery<DQHubSummary, Error>({
    queryKey: dqKeys.hubSummary(),
    queryFn: getDQHubSummary,
  })
}

/**
 * Run DQ checks for a config.
 */
export function useRunDQConfig() {
  const queryClient = useQueryClient()

  return useMutation<DQRunResult, Error, { configId: number; snapshotDate?: string }>({
    mutationFn: ({ configId, snapshotDate }) => runDQConfig(configId, snapshotDate),
    onSuccess: () => {
      // Invalidate breaches and hub summary after running checks
      queryClient.invalidateQueries({ queryKey: dqKeys.breaches() })
      queryClient.invalidateQueries({ queryKey: dqKeys.hubSummary() })
    },
  })
}

/**
 * Update breach status.
 */
export function useUpdateBreachStatus() {
  const queryClient = useQueryClient()

  return useMutation<DQBreach, Error, { breachId: number; data: BreachStatusUpdate }>({
    mutationFn: ({ breachId, data }) => updateDQBreachStatus(breachId, data),
    onSuccess: (updatedBreach) => {
      // Update the breach in cache
      queryClient.setQueryData(dqKeys.breachDetail(updatedBreach.id), updatedBreach)
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: dqKeys.breaches() })
      queryClient.invalidateQueries({ queryKey: dqKeys.hubSummary() })
    },
  })
}
