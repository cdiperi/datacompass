import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import {
  getAuthStatus,
  getCurrentUser,
  login as apiLogin,
  refreshTokens as apiRefreshTokens,
  setTokens,
  clearTokens,
  getRefreshToken,
} from '../api/client'
import type { AuthUser } from '../api/types'

export interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  authDisabled: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<boolean>
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [authDisabled, setAuthDisabled] = useState(false)

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setIsAuthenticated(false)
  }, [])

  const refreshToken = useCallback(async (): Promise<boolean> => {
    const refreshTokenValue = getRefreshToken()
    if (!refreshTokenValue) {
      return false
    }

    try {
      const response = await apiRefreshTokens({ refresh_token: refreshTokenValue })
      setTokens(response.access_token, response.refresh_token)
      return true
    } catch {
      logout()
      return false
    }
  }, [logout])

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const tokenResponse = await apiLogin({ email, password })
    setTokens(tokenResponse.access_token, tokenResponse.refresh_token)

    // Fetch user details after successful login
    const authResponse = await getCurrentUser()
    if (authResponse.user) {
      setUser(authResponse.user)
      setIsAuthenticated(true)
    }
  }, [])

  // Initialize auth state on mount
  useEffect(() => {
    async function initAuth() {
      try {
        // First check if auth is enabled
        const statusResponse = await getAuthStatus()

        if (statusResponse.auth_mode === 'disabled') {
          // Auth is disabled - treat as authenticated
          setAuthDisabled(true)
          setIsAuthenticated(true)
          setUser(null)
          setIsLoading(false)
          return
        }

        // Auth is enabled - check if we have a valid token
        const refreshTokenValue = getRefreshToken()
        if (!refreshTokenValue) {
          // No token, not authenticated
          setIsLoading(false)
          return
        }

        // Try to get current user with existing token
        try {
          const userResponse = await getCurrentUser()
          if (userResponse.user) {
            setUser(userResponse.user)
            setIsAuthenticated(true)
          }
        } catch {
          // Token might be expired, try to refresh
          const refreshed = await refreshToken()
          if (refreshed) {
            // Try again with new token
            try {
              const userResponse = await getCurrentUser()
              if (userResponse.user) {
                setUser(userResponse.user)
                setIsAuthenticated(true)
              }
            } catch {
              // Still failed, clear tokens
              logout()
            }
          }
        }
      } catch {
        // Failed to get auth status - assume auth is disabled or backend is down
        console.error('Failed to check auth status')
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [logout, refreshToken])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        authDisabled,
        login,
        logout,
        refreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
