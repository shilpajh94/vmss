import heroImage from "../../../assets/images/lobby-hero.png"
import { CalendarIcon, SearchIcon } from "../../../assets/icons"
import { PortalFooter } from "../../components/PortalFooter"
import { PortalHeader } from "../../components/PortalHeader"
import { ActionCard } from "./Components/ActionCard"
import { PortalHero } from "./Components/PortalHero"

export function VisitorPortalLandingPage() {
  return (
    <div className="flex min-h-screen w-full flex-col justify-between bg-[#f8fafc]">
      <div className="flex w-full flex-col">
        <PortalHeader />
        <div className="relative flex w-full flex-col">
          <div aria-hidden className="absolute inset-0">
            <img src={heroImage} alt="" className="size-full object-cover" />
            <div className="absolute inset-0 bg-primary/55" />
          </div>
          <PortalHero />
          <div className="relative flex w-full justify-center gap-8 px-12 pb-[100px]">
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
      </div>
      <PortalFooter />
    </div>
  )
}
