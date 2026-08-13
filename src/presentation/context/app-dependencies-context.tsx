import { createContext, useContext, useState, type ReactNode } from 'react'
import { createApp, type AppDependencies } from '../../composition-root'

const AppDependenciesContext = createContext<AppDependencies | null>(null)

export function AppDependenciesProvider({ children }: { children: ReactNode }) {
  const [dependencies] = useState<AppDependencies>(() => createApp())

  return <AppDependenciesContext.Provider value={dependencies}>{children}</AppDependenciesContext.Provider>
}

export function useAppDependencies(): AppDependencies {
  const dependencies = useContext(AppDependenciesContext)

  if (!dependencies) {
    throw new Error('useAppDependencies must be used within an AppDependenciesProvider')
  }

  return dependencies
}
