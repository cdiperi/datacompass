import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { BrowsePage } from './pages/BrowsePage'
import { ObjectDetailPage } from './pages/ObjectDetailPage'
import { SearchResultsPage } from './pages/SearchResultsPage'
import { DQHubPage } from './pages/DQHubPage'
import { DeprecationHubPage } from './pages/DeprecationHubPage'
import { SchedulerHubPage } from './pages/SchedulerHubPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#1677ff',
          },
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="browse" element={<BrowsePage />} />
              <Route path="objects/:id" element={<ObjectDetailPage />} />
              <Route path="search" element={<SearchResultsPage />} />
              <Route path="dq" element={<DQHubPage />} />
              <Route path="deprecation" element={<DeprecationHubPage />} />
              <Route path="scheduler" element={<SchedulerHubPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  )
}

export default App
