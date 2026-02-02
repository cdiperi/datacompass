/**
 * TanStack Query hooks for Deprecation data.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addObjectToCampaign,
  createCampaign,
  deleteCampaign,
  getCampaign,
  getCampaignImpact,
  getCampaigns,
  getDeprecationHubSummary,
  getDeprecations,
  removeObjectFromCampaign,
  updateCampaign,
} from '../api/client'
import type {
  CampaignCreate,
  CampaignDetailResponse,
  CampaignFilters,
  CampaignImpactSummary,
  CampaignListItem,
  CampaignUpdate,
  DeprecationCreate,
  DeprecationFilters,
  DeprecationHubSummary,
  DeprecationResponse,
} from '../api/types'

export const deprecationKeys = {
  all: ['deprecation'] as const,
  campaigns: () => [...deprecationKeys.all, 'campaigns'] as const,
  campaignList: (filters: CampaignFilters) =>
    [...deprecationKeys.campaigns(), 'list', filters] as const,
  campaignDetail: (id: number) =>
    [...deprecationKeys.campaigns(), 'detail', id] as const,
  campaignImpact: (id: number, depth: number) =>
    [...deprecationKeys.campaigns(), 'impact', id, depth] as const,
  deprecations: () => [...deprecationKeys.all, 'deprecations'] as const,
  deprecationList: (filters: DeprecationFilters) =>
    [...deprecationKeys.deprecations(), 'list', filters] as const,
  hubSummary: () => [...deprecationKeys.all, 'hub', 'summary'] as const,
}

/**
 * Fetch campaigns list.
 */
export function useCampaigns(filters: CampaignFilters = {}) {
  return useQuery<CampaignListItem[], Error>({
    queryKey: deprecationKeys.campaignList(filters),
    queryFn: () => getCampaigns(filters),
  })
}

/**
 * Fetch single campaign with deprecations.
 */
export function useCampaign(campaignId: number) {
  return useQuery<CampaignDetailResponse, Error>({
    queryKey: deprecationKeys.campaignDetail(campaignId),
    queryFn: () => getCampaign(campaignId),
    enabled: !!campaignId,
  })
}

/**
 * Fetch campaign impact analysis.
 */
export function useCampaignImpact(campaignId: number, depth = 3) {
  return useQuery<CampaignImpactSummary, Error>({
    queryKey: deprecationKeys.campaignImpact(campaignId, depth),
    queryFn: () => getCampaignImpact(campaignId, depth),
    enabled: !!campaignId,
  })
}

/**
 * Fetch deprecations list.
 */
export function useDeprecations(filters: DeprecationFilters = {}) {
  return useQuery<DeprecationResponse[], Error>({
    queryKey: deprecationKeys.deprecationList(filters),
    queryFn: () => getDeprecations(filters),
  })
}

/**
 * Fetch deprecation hub summary.
 */
export function useDeprecationHubSummary() {
  return useQuery<DeprecationHubSummary, Error>({
    queryKey: deprecationKeys.hubSummary(),
    queryFn: getDeprecationHubSummary,
  })
}

/**
 * Create a new campaign.
 */
export function useCreateCampaign() {
  const queryClient = useQueryClient()

  return useMutation<CampaignDetailResponse, Error, CampaignCreate>({
    mutationFn: createCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deprecationKeys.campaigns() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.hubSummary() })
    },
  })
}

/**
 * Update a campaign.
 */
export function useUpdateCampaign() {
  const queryClient = useQueryClient()

  return useMutation<
    CampaignDetailResponse,
    Error,
    { campaignId: number; data: CampaignUpdate }
  >({
    mutationFn: ({ campaignId, data }) => updateCampaign(campaignId, data),
    onSuccess: (updatedCampaign) => {
      queryClient.setQueryData(
        deprecationKeys.campaignDetail(updatedCampaign.id),
        updatedCampaign
      )
      queryClient.invalidateQueries({ queryKey: deprecationKeys.campaigns() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.hubSummary() })
    },
  })
}

/**
 * Delete a campaign.
 */
export function useDeleteCampaign() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: deleteCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deprecationKeys.campaigns() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.hubSummary() })
    },
  })
}

/**
 * Add object to campaign.
 */
export function useAddObjectToCampaign() {
  const queryClient = useQueryClient()

  return useMutation<
    DeprecationResponse,
    Error,
    { campaignId: number; data: DeprecationCreate }
  >({
    mutationFn: ({ campaignId, data }) => addObjectToCampaign(campaignId, data),
    onSuccess: (_, { campaignId }) => {
      queryClient.invalidateQueries({
        queryKey: deprecationKeys.campaignDetail(campaignId),
      })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.deprecations() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.hubSummary() })
    },
  })
}

/**
 * Remove object from campaign.
 */
export function useRemoveObjectFromCampaign() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: removeObjectFromCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deprecationKeys.campaigns() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.deprecations() })
      queryClient.invalidateQueries({ queryKey: deprecationKeys.hubSummary() })
    },
  })
}
