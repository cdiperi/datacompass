import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ObjectDetailPage } from '../src/pages/ObjectDetailPage'
import * as objectsHook from '../src/hooks/useObjects'
import * as lineageHook from '../src/hooks/useLineage'
import * as dqHook from '../src/hooks/useDQ'
import type { CatalogObjectDetail, LineageGraph, DQConfigListItem, DQBreach } from '../src/api/types'

// Mock lineage data
const mockLineageGraph: LineageGraph = {
  root: {
    id: 1,
    source_name: 'prod',
    schema_name: 'public',
    object_name: 'users',
    object_type: 'TABLE',
    distance: 0,
  },
  nodes: [],
  external_nodes: [],
  edges: [],
  direction: 'upstream',
  depth: 3,
  truncated: false,
}

const mockObject: CatalogObjectDetail = {
  id: 1,
  source_id: 1,
  source_name: 'prod',
  schema_name: 'public',
  object_name: 'users',
  object_type: 'TABLE',
  source_metadata: {
    row_count: 1000000,
    size_bytes: 536870912, // 512 MB
  },
  user_metadata: {
    description: 'Contains user account information',
    tags: ['pii', 'core'],
  },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
  deleted_at: null,
  columns: [
    {
      column_name: 'id',
      data_type: 'INTEGER',
      nullable: false,
      description: 'Primary key',
    },
    {
      column_name: 'email',
      data_type: 'VARCHAR(255)',
      nullable: false,
      description: 'User email address',
    },
    {
      column_name: 'name',
      data_type: 'VARCHAR(100)',
      nullable: true,
      description: null,
    },
  ],
}

function renderWithProviders(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/catalog/:source/:schema/:object" element={<ObjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ObjectDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Mock useLineage to prevent errors in LineageList component
    vi.spyOn(lineageHook, 'useLineage').mockReturnValue({
      data: mockLineageGraph,
      isLoading: false,
      error: null,
    } as ReturnType<typeof lineageHook.useLineage>)
    // Mock DQ hooks
    vi.spyOn(dqHook, 'useDQConfigs').mockReturnValue({
      data: [] as DQConfigListItem[],
      isLoading: false,
      error: null,
    } as ReturnType<typeof dqHook.useDQConfigs>)
    vi.spyOn(dqHook, 'useDQBreaches').mockReturnValue({
      data: [] as DQBreach[],
      isLoading: false,
      error: null,
    } as ReturnType<typeof dqHook.useDQBreaches>)
  })

  it('displays loading state', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // Ant Design Spin renders multiple spinner elements
    const spinners = document.querySelectorAll('.ant-spin')
    expect(spinners.length).toBeGreaterThan(0)
  })

  it('displays object name as title', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    expect(screen.getByRole('heading', { level: 2, name: 'users' })).toBeInTheDocument()
  })

  it('displays object metadata in Overview tab', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // 'prod' and 'public' appear in both breadcrumb and metadata
    expect(screen.getAllByText('prod').length).toBeGreaterThan(0)
    expect(screen.getAllByText('public').length).toBeGreaterThan(0)
    expect(screen.getByText('TABLE')).toBeInTheDocument()
  })

  it('displays description in Overview tab', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    expect(screen.getByText('Contains user account information')).toBeInTheDocument()
  })

  it('displays tags in Overview tab', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    expect(screen.getByText('pii')).toBeInTheDocument()
    expect(screen.getByText('core')).toBeInTheDocument()
  })

  it('shows columns section with column count in Overview tab', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // The Columns section shows the count in the Overview tab
    expect(screen.getByText('Columns (3)')).toBeInTheDocument()
  })

  it('displays row count and size statistics when available', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // Row count should be displayed (1M for 1,000,000)
    expect(screen.getByText('Row Count')).toBeInTheDocument()
    expect(screen.getByText('1M')).toBeInTheDocument()

    // Size should be displayed (512 MB)
    expect(screen.getByText('Size')).toBeInTheDocument()
    expect(screen.getByText('512.00 MB')).toBeInTheDocument()
  })

  it('displays error when loading fails', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Object not found'),
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/nonexistent')

    expect(screen.getByText('Error loading object')).toBeInTheDocument()
    expect(screen.getByText('Object not found')).toBeInTheDocument()
  })

  it('displays not found when object is null', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/nonexistent')

    expect(screen.getByText('Object not found')).toBeInTheDocument()
  })

  it('displays breadcrumb navigation with Catalog link', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // Check for Catalog in breadcrumb
    expect(screen.getByText('Catalog')).toBeInTheDocument()
  })

  it('shows Overview tab as the default active tab', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('/catalog/prod/public/users')

    // Overview should be the active tab
    const overviewTab = screen.getByRole('tab', { name: /Overview/i })
    expect(overviewTab).toHaveAttribute('aria-selected', 'true')
  })
})
