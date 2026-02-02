import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HomePage } from '../src/pages/HomePage'
import * as searchHook from '../src/hooks/useSearch'

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
    // Mock the search hook to return empty results
    vi.spyOn(searchHook, 'useDebouncedSearch').mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      error: null,
    } as ReturnType<typeof searchHook.useDebouncedSearch>)
  })

  it('renders Data Compass branding', () => {
    renderWithProviders(<HomePage />)

    expect(screen.getByText('Data Compass')).toBeInTheDocument()
  })

  it('renders search bar with placeholder', () => {
    renderWithProviders(<HomePage />)

    expect(screen.getByPlaceholderText('Search for tables, views, columns...')).toBeInTheDocument()
  })

  it('renders tagline', () => {
    renderWithProviders(<HomePage />)

    expect(screen.getByText('Navigate your data with confidence')).toBeInTheDocument()
  })
})
