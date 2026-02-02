import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HomePage } from '../src/pages/HomePage'
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
  {
    id: 2,
    name: 'dev',
    display_name: null,
    source_type: 'snowflake',
    is_active: false,
    last_scan_at: null,
    last_scan_status: null,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

const mockObjects: CatalogObjectSummary[] = [
  {
    id: 1,
    source_name: 'prod',
    schema_name: 'public',
    object_name: 'users',
    object_type: 'TABLE',
    description: 'User table',
    column_count: 5,
  },
]

function renderWithProviders(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{component}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders dashboard title', () => {
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

    renderWithProviders(<HomePage />)

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('displays loading state', () => {
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

    renderWithProviders(<HomePage />)

    // "Data Sources" appears in both the statistic title and section header
    expect(screen.getAllByText('Data Sources').length).toBeGreaterThan(0)
  })

  it('displays sources when loaded', () => {
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

    renderWithProviders(<HomePage />)

    expect(screen.getByText('Production DB')).toBeInTheDocument()
    expect(screen.getByText('dev')).toBeInTheDocument()
  })

  it('displays empty state when no sources', () => {
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

    renderWithProviders(<HomePage />)

    expect(screen.getByText('No data sources configured')).toBeInTheDocument()
  })

  it('displays error when loading fails', () => {
    vi.spyOn(sourcesHook, 'useSources').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
    } as ReturnType<typeof sourcesHook.useSources>)
    vi.spyOn(objectsHook, 'useObjects').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObjects>)

    renderWithProviders(<HomePage />)

    expect(screen.getByText('Error loading sources')).toBeInTheDocument()
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })
})
