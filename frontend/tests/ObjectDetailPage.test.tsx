import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ObjectDetailPage } from '../src/pages/ObjectDetailPage'
import * as objectsHook from '../src/hooks/useObjects'
import * as lineageHook from '../src/hooks/useLineage'
import type { CatalogObjectDetail, LineageGraph } from '../src/api/types'

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

function renderWithProviders(objectId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/objects/${objectId}`]}>
        <Routes>
          <Route path="/objects/:id" element={<ObjectDetailPage />} />
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
  })

  it('displays loading state', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

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

    renderWithProviders('1')

    expect(screen.getByRole('heading', { level: 2, name: 'users' })).toBeInTheDocument()
  })

  it('displays object metadata', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

    // 'prod' and 'public' appear in both breadcrumb and metadata
    expect(screen.getAllByText('prod').length).toBeGreaterThan(0)
    expect(screen.getAllByText('public').length).toBeGreaterThan(0)
    expect(screen.getByText('TABLE')).toBeInTheDocument()
  })

  it('displays description', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

    expect(screen.getByText('Contains user account information')).toBeInTheDocument()
  })

  it('displays tags', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

    expect(screen.getByText('pii')).toBeInTheDocument()
    expect(screen.getByText('core')).toBeInTheDocument()
  })

  it('displays columns table', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

    expect(screen.getByText('Columns (3)')).toBeInTheDocument()
    expect(screen.getByText('id')).toBeInTheDocument()
    expect(screen.getByText('email')).toBeInTheDocument()
    expect(screen.getByText('name')).toBeInTheDocument()
    expect(screen.getByText('INTEGER')).toBeInTheDocument()
    expect(screen.getByText('VARCHAR(255)')).toBeInTheDocument()
  })

  it('displays error when loading fails', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Object not found'),
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('999')

    expect(screen.getByText('Error loading object')).toBeInTheDocument()
    expect(screen.getByText('Object not found')).toBeInTheDocument()
  })

  it('displays not found when object is null', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('999')

    expect(screen.getByText('Object not found')).toBeInTheDocument()
  })

  it('displays breadcrumb navigation', () => {
    vi.spyOn(objectsHook, 'useObject').mockReturnValue({
      data: mockObject,
      isLoading: false,
      error: null,
    } as ReturnType<typeof objectsHook.useObject>)

    renderWithProviders('1')

    // Check for breadcrumb items (may appear in links or as text)
    expect(screen.getByText('Browse')).toBeInTheDocument()
  })
})
