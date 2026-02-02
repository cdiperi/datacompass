import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowsePage } from '../src/pages/BrowsePage'
import * as sourcesHook from '../src/hooks/useSources'
import * as objectsHook from '../src/hooks/useObjects'
import type { DataSource, CatalogObjectSummary } from '../src/api/types'

const mockSources: DataSource[] = [
  {
    id: 1,
    name: 'prod',
    display_name: 'Production DB',
    source_type: 'databricks',
    is_active: true,
    last_scan_at: '2026-01-15T10:00:00Z',
    last_scan_status: 'success',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
]

const mockObjects: CatalogObjectSummary[] = [
  {
    id: 1,
    source_name: 'prod',
    schema_name: 'public',
    object_name: 'users',
    object_type: 'TABLE',
    description: 'User accounts table',
    column_count: 5,
  },
  {
    id: 2,
    source_name: 'prod',
    schema_name: 'public',
    object_name: 'orders',
    object_type: 'TABLE',
    description: null,
    column_count: 8,
  },
  {
    id: 3,
    source_name: 'prod',
    schema_name: 'analytics',
    object_name: 'daily_metrics',
    object_type: 'VIEW',
    description: 'Daily aggregated metrics',
    column_count: 12,
  },
]

function renderWithProviders(
  component: React.ReactElement,
  { initialEntries = ['/browse'] } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{component}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('BrowsePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders browse catalog title', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getByText('Browse Catalog')).toBeInTheDocument()
  })

  it('displays objects in table', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: mockSources,
      isLoading: false,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: mockObjects,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getByText('users')).toBeInTheDocument()
    expect(screen.getByText('orders')).toBeInTheDocument()
    expect(screen.getByText('daily_metrics')).toBeInTheDocument()
  })

  it('displays object types as tags', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: mockSources,
      isLoading: false,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: mockObjects,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getAllByText('TABLE')).toHaveLength(2)
    expect(screen.getByText('VIEW')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getByText('Browse Catalog')).toBeInTheDocument()
  })

  it('displays error when loading fails', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load objects'),
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getByText('Error loading objects')).toBeInTheDocument()
    expect(screen.getByText('Failed to load objects')).toBeInTheDocument()
  })

  it('displays descriptions and placeholder for missing ones', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: mockSources,
      isLoading: false,
      error: null,
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: mockObjects,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<BrowsePage />)

    expect(screen.getByText('User accounts table')).toBeInTheDocument()
    expect(screen.getByText('Daily aggregated metrics')).toBeInTheDocument()
    expect(screen.getByText('No description')).toBeInTheDocument()
  })
})
