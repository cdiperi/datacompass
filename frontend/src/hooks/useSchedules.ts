/**
 * TanStack Query hooks for Scheduling data.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createSchedule,
  deleteSchedule,
  getSchedule,
  getScheduleRuns,
  getSchedules,
  getSchedulerHubSummary,
  runScheduleNow,
  updateSchedule,
} from '../api/client'
import type {
  Schedule,
  ScheduleCreate,
  ScheduleFilters,
  ScheduleRun,
  ScheduleUpdate,
  SchedulerHubSummary,
} from '../api/types'

export const scheduleKeys = {
  all: ['schedules'] as const,
  lists: () => [...scheduleKeys.all, 'list'] as const,
  list: (filters: ScheduleFilters) => [...scheduleKeys.lists(), filters] as const,
  details: () => [...scheduleKeys.all, 'detail'] as const,
  detail: (id: number) => [...scheduleKeys.details(), id] as const,
  runs: (id: number) => [...scheduleKeys.all, 'runs', id] as const,
  hubSummary: () => [...scheduleKeys.all, 'hub', 'summary'] as const,
}

/**
 * Fetch schedules list.
 */
export function useSchedules(filters: ScheduleFilters = {}) {
  return useQuery<Schedule[], Error>({
    queryKey: scheduleKeys.list(filters),
    queryFn: () => getSchedules(filters),
  })
}

/**
 * Fetch single schedule.
 */
export function useSchedule(scheduleId: number) {
  return useQuery<Schedule, Error>({
    queryKey: scheduleKeys.detail(scheduleId),
    queryFn: () => getSchedule(scheduleId),
    enabled: !!scheduleId,
  })
}

/**
 * Fetch schedule runs.
 */
export function useScheduleRuns(scheduleId: number, limit = 20) {
  return useQuery<ScheduleRun[], Error>({
    queryKey: scheduleKeys.runs(scheduleId),
    queryFn: () => getScheduleRuns(scheduleId, limit),
    enabled: !!scheduleId,
  })
}

/**
 * Fetch scheduler hub summary.
 */
export function useSchedulerHubSummary() {
  return useQuery<SchedulerHubSummary, Error>({
    queryKey: scheduleKeys.hubSummary(),
    queryFn: getSchedulerHubSummary,
  })
}

/**
 * Create a new schedule.
 */
export function useCreateSchedule() {
  const queryClient = useQueryClient()

  return useMutation<Schedule, Error, ScheduleCreate>({
    mutationFn: createSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.hubSummary() })
    },
  })
}

/**
 * Update a schedule.
 */
export function useUpdateSchedule() {
  const queryClient = useQueryClient()

  return useMutation<Schedule, Error, { scheduleId: number; data: ScheduleUpdate }>({
    mutationFn: ({ scheduleId, data }) => updateSchedule(scheduleId, data),
    onSuccess: (updatedSchedule) => {
      queryClient.setQueryData(scheduleKeys.detail(updatedSchedule.id), updatedSchedule)
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.hubSummary() })
    },
  })
}

/**
 * Delete a schedule.
 */
export function useDeleteSchedule() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: deleteSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.hubSummary() })
    },
  })
}

/**
 * Run a schedule immediately.
 */
export function useRunScheduleNow() {
  const queryClient = useQueryClient()

  return useMutation<ScheduleRun, Error, number>({
    mutationFn: runScheduleNow,
    onSuccess: (_, scheduleId) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.detail(scheduleId) })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.runs(scheduleId) })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.hubSummary() })
    },
  })
}
