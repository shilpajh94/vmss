import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AdminTopBarBreadcrumbItem } from '../components/AdminTopBar'

export interface PageHeader {
  description?: string
  breadcrumb?: AdminTopBarBreadcrumbItem[]
}

interface PageHeaderContextValue {
  header: PageHeader
  setHeader: (header: PageHeader) => void
}

const PageHeaderContext = createContext<PageHeaderContextValue | undefined>(undefined)

// Lets the persistent AdminLayout own the one AdminTopBar instance while each
// admin page still controls its own description/breadcrumb text, without the
// page needing to render (or remount) the top bar itself.
export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [header, setHeader] = useState<PageHeader>({})
  const value = useMemo(() => ({ header, setHeader }), [header])

  return <PageHeaderContext.Provider value={value}>{children}</PageHeaderContext.Provider>
}

export function usePageHeaderContext(): PageHeaderContextValue {
  const context = useContext(PageHeaderContext)
  if (!context) {
    throw new Error('usePageHeaderContext must be used within a PageHeaderProvider')
  }
  return context
}

// Called by a page to publish its own header content into the persistent
// AdminLayout's AdminTopBar. Re-publishes whenever the description or
// breadcrumb labels change, so a breadcrumb that depends on data loaded after
// mount (e.g. a role's name) still updates the visible top bar once it arrives.
export function usePageHeader(header: PageHeader): void {
  const { setHeader } = usePageHeaderContext()
  const breadcrumbKey = header.breadcrumb?.map((item) => `${item.label}:${item.isActive ?? false}`).join('|')

  useEffect(() => {
    setHeader(header)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [header.description, breadcrumbKey])
}
