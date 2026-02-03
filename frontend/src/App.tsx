import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import { AuthProvider } from './context/AuthContext'
import { SidebarProvider } from './context/SidebarContext'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { HomePage } from './pages/HomePage'
import { BrowsePage } from './pages/BrowsePage'
import { ObjectDetailPage } from './pages/ObjectDetailPage'
import { ObjectRedirect } from './pages/ObjectRedirect'
import { SearchResultsPage } from './pages/SearchResultsPage'
import { DQHubPage } from './pages/DQHubPage'
import { DeprecationHubPage } from './pages/DeprecationHubPage'
import { SchedulerHubPage } from './pages/SchedulerHubPage'
import { LoginPage } from './pages/LoginPage'

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
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: '#1677ff',
            },
          }}
        >
          <SidebarProvider>
            <BrowserRouter>
              <Routes>
                {/* Login route - outside protected area */}
                <Route path="/login" element={<LoginPage />} />

                {/* Protected routes with layout */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <Layout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<HomePage />} />

                  {/* Catalog hierarchy */}
                  <Route path="catalog" element={<BrowsePage />} />
                  <Route path="catalog/:source" element={<BrowsePage />} />
                  <Route path="catalog/:source/:schema" element={<BrowsePage />} />
                  <Route path="catalog/:source/:schema/:object" element={<ObjectDetailPage />} />

                  {/* Feature hubs */}
                  <Route path="search" element={<SearchResultsPage />} />
                  <Route path="dq" element={<DQHubPage />} />
                  <Route path="deprecation" element={<DeprecationHubPage />} />
                  <Route path="scheduler" element={<SchedulerHubPage />} />

                  {/* Legacy redirects */}
                  <Route path="objects/:id" element={<ObjectRedirect />} />
                  <Route path="browse" element={<Navigate to="/catalog" replace />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </SidebarProvider>
        </ConfigProvider>
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App
