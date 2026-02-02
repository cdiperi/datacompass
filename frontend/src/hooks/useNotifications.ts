/**
 * TanStack Query hooks for Notification data.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createNotificationChannel,
  createNotificationRule,
  deleteNotificationChannel,
  deleteNotificationRule,
  getNotificationChannel,
  getNotificationChannels,
  getNotificationLog,
  getNotificationRule,
  getNotificationRules,
  testNotificationChannel,
  updateNotificationChannel,
  updateNotificationRule,
} from '../api/client'
import type {
  ChannelCreate,
  ChannelFilters,
  ChannelUpdate,
  NotificationChannel,
  NotificationLogEntry,
  NotificationLogFilters,
  NotificationRule,
  RuleCreate,
  RuleFilters,
  RuleUpdate,
} from '../api/types'

export const notificationKeys = {
  all: ['notifications'] as const,
  channels: () => [...notificationKeys.all, 'channels'] as const,
  channelList: (filters: ChannelFilters) =>
    [...notificationKeys.channels(), 'list', filters] as const,
  channelDetail: (id: number) => [...notificationKeys.channels(), 'detail', id] as const,
  rules: () => [...notificationKeys.all, 'rules'] as const,
  ruleList: (filters: RuleFilters) => [...notificationKeys.rules(), 'list', filters] as const,
  ruleDetail: (id: number) => [...notificationKeys.rules(), 'detail', id] as const,
  log: (filters: NotificationLogFilters) => [...notificationKeys.all, 'log', filters] as const,
}

// =============================================================================
// Channel Hooks
// =============================================================================

/**
 * Fetch notification channels list.
 */
export function useNotificationChannels(filters: ChannelFilters = {}) {
  return useQuery<NotificationChannel[], Error>({
    queryKey: notificationKeys.channelList(filters),
    queryFn: () => getNotificationChannels(filters),
  })
}

/**
 * Fetch single notification channel.
 */
export function useNotificationChannel(channelId: number) {
  return useQuery<NotificationChannel, Error>({
    queryKey: notificationKeys.channelDetail(channelId),
    queryFn: () => getNotificationChannel(channelId),
    enabled: !!channelId,
  })
}

/**
 * Create a notification channel.
 */
export function useCreateNotificationChannel() {
  const queryClient = useQueryClient()

  return useMutation<NotificationChannel, Error, ChannelCreate>({
    mutationFn: createNotificationChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.channels() })
    },
  })
}

/**
 * Update a notification channel.
 */
export function useUpdateNotificationChannel() {
  const queryClient = useQueryClient()

  return useMutation<NotificationChannel, Error, { channelId: number; data: ChannelUpdate }>({
    mutationFn: ({ channelId, data }) => updateNotificationChannel(channelId, data),
    onSuccess: (updatedChannel) => {
      queryClient.setQueryData(notificationKeys.channelDetail(updatedChannel.id), updatedChannel)
      queryClient.invalidateQueries({ queryKey: notificationKeys.channels() })
    },
  })
}

/**
 * Delete a notification channel.
 */
export function useDeleteNotificationChannel() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: deleteNotificationChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.channels() })
    },
  })
}

/**
 * Test a notification channel.
 */
export function useTestNotificationChannel() {
  return useMutation<{ success: boolean; message: string }, Error, number>({
    mutationFn: testNotificationChannel,
  })
}

// =============================================================================
// Rule Hooks
// =============================================================================

/**
 * Fetch notification rules list.
 */
export function useNotificationRules(filters: RuleFilters = {}) {
  return useQuery<NotificationRule[], Error>({
    queryKey: notificationKeys.ruleList(filters),
    queryFn: () => getNotificationRules(filters),
  })
}

/**
 * Fetch single notification rule.
 */
export function useNotificationRule(ruleId: number) {
  return useQuery<NotificationRule, Error>({
    queryKey: notificationKeys.ruleDetail(ruleId),
    queryFn: () => getNotificationRule(ruleId),
    enabled: !!ruleId,
  })
}

/**
 * Create a notification rule.
 */
export function useCreateNotificationRule() {
  const queryClient = useQueryClient()

  return useMutation<NotificationRule, Error, RuleCreate>({
    mutationFn: createNotificationRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.rules() })
    },
  })
}

/**
 * Update a notification rule.
 */
export function useUpdateNotificationRule() {
  const queryClient = useQueryClient()

  return useMutation<NotificationRule, Error, { ruleId: number; data: RuleUpdate }>({
    mutationFn: ({ ruleId, data }) => updateNotificationRule(ruleId, data),
    onSuccess: (updatedRule) => {
      queryClient.setQueryData(notificationKeys.ruleDetail(updatedRule.id), updatedRule)
      queryClient.invalidateQueries({ queryKey: notificationKeys.rules() })
    },
  })
}

/**
 * Delete a notification rule.
 */
export function useDeleteNotificationRule() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: deleteNotificationRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.rules() })
    },
  })
}

// =============================================================================
// Log Hooks
// =============================================================================

/**
 * Fetch notification log entries.
 */
export function useNotificationLog(filters: NotificationLogFilters = {}) {
  return useQuery<NotificationLogEntry[], Error>({
    queryKey: notificationKeys.log(filters),
    queryFn: () => getNotificationLog(filters),
  })
}
