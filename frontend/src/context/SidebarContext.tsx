import { createContext, useState, useEffect, type ReactNode } from 'react'

export interface SidebarContextType {
  collapsed: boolean
  toggleCollapsed: () => void
  setCollapsed: (collapsed: boolean) => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

const STORAGE_KEY = 'datacompass-sidebar-collapsed'

interface SidebarProviderProps {
  children: ReactNode
}

export function SidebarProvider({ children }: SidebarProviderProps) {
  const [collapsed, setCollapsedState] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    // Default to collapsed (true) for search-first experience
    return stored !== null ? stored === 'true' : true
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed))
  }, [collapsed])

  const toggleCollapsed = () => {
    setCollapsedState((prev) => !prev)
  }

  const setCollapsed = (value: boolean) => {
    setCollapsedState(value)
  }

  return (
    <SidebarContext.Provider value={{ collapsed, toggleCollapsed, setCollapsed }}>
      {children}
    </SidebarContext.Provider>
  )
}
