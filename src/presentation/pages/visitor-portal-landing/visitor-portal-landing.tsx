import { CalendarIcon, SearchIcon } from "../../../assets/icons"
import { SplitScreenLayout } from "../../components/layout/SplitScreenLayout"
import { VISITOR_BRAND, visitorFooterLinks } from "../../components/layout/visitor-brand"
import { ActionCard } from "./Components/ActionCard"

export function VisitorPortalLandingPage() {
  return (
    <SplitScreenLayout portalLabel="Visitor Portal" brand={VISITOR_BRAND} footerLinks={visitorFooterLinks()} contentClassName="max-w-[480px]">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-[30px] leading-tight font-bold text-text xshort:text-[26px]">Welcome</h1>
        <p className="font-body text-[14px] leading-normal text-text-muted">How can we help you today?</p>
      </div>
      <div className="flex flex-col gap-4 xshort:gap-3">
        <ActionCard
          icon={CalendarIcon}
          title="Request a Visit"
          description="Schedule a single or group visit beforehand. Provide host details and sign required safety documents instantly."
          to="/visitor/request"
          buttonLabel="Request Visit"
          variant="filled"
        />
        <ActionCard
          icon={SearchIcon}
          title="Track Your Visit"
          description="Check the status of your visitor request, update entry specifications, and view host approval details."
          to="/visitor/track"
          buttonLabel="Track Request"
          variant="outlined"
        />
      </div>
    </SplitScreenLayout>
  )
}
