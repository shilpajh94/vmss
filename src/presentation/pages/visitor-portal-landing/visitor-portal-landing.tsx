import { HeroImage } from "../../components/HeroImage"
import { CalendarIcon, SearchIcon } from "../../../assets/icons"
import { PortalFooter } from "../../components/PortalFooter"
import { PortalHeader } from "../../components/PortalHeader"
import { ActionCard } from "./Components/ActionCard"
import { PortalHero } from "./Components/PortalHero"

export function VisitorPortalLandingPage() {
  return (
    <div className="flex min-h-dvh w-full flex-col bg-surface-muted">
      <PortalHeader />
      <div className="relative flex w-full flex-1 flex-col justify-center">
        <div aria-hidden className="absolute inset-0">
          <HeroImage />
          <div className="absolute inset-0 bg-primary/55" />
        </div>
        <PortalHero />
        <div className="relative flex w-full flex-col items-center gap-4 px-4 pb-12 md:gap-8 md:px-12 lg:flex-row lg:items-stretch lg:justify-center lg:pb-10">
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
      </div>
      <PortalFooter />
    </div>
  )
}
