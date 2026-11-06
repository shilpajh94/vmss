## Purpose

Defines the one split-screen layout every public page (visitor portal, visitor request and tracking flows, sign-in pages, and the not-found and error pages) is built on, so the whole public side of the product looks and behaves the same.

## ADDED Requirements

### Requirement: Every public page uses the split-screen layout
The system SHALL render each of the following screens on the shared split-screen layout:
- the visitor portal landing page;
- the OTP request, OTP verify, history lookup and return-visit history screens;
- every step of the visitor registration wizard, including review and confirmation;
- the track page in its lookup, loading, result and no-result states;
- the admin and staff sign-in pages;
- the not-found page;
- the route error page.

The layout SHALL be:
- **From 1024px wide:** a navy brand panel on the left and a light content panel on the right.
- **Below 1024px wide:** a navy top strip with the Visimio on-dark logo and the page's portal tag, with the content panel below it.

No public screen SHALL show the former white header bar, the white footer bar, or a lobby photo behind its content.

#### Scenario: OTP request screen on a laptop
- **WHEN** a visitor opens `/visitor/request` at 1440×900
- **THEN** the navy brand panel is on the left and the "Request a visit" form is on the right, with no white header bar above it

#### Scenario: Track page on a phone
- **WHEN** a visitor opens `/visitor/track` at 360×640
- **THEN** the navy top strip with the Visimio logo is at the top, the tracking form is below it, and no lobby photo is shown

#### Scenario: Not-found page
- **WHEN** a visitor opens an unknown path at 1440×900
- **THEN** the "Page not found" message and its home link are in the content panel, beside the navy brand panel

### Requirement: Only the content panel scrolls
The page itself SHALL NOT scroll on any public screen. When the content is taller than the viewport, only the content panel SHALL scroll. The brand panel, or the top strip below 1024px, SHALL stay in place. No content SHALL be clipped or unreachable.

When a screen's content fits, the content panel SHALL centre it vertically. When a screen's content can grow long, it SHALL start at the top of the content panel instead. Screens that can grow long are the wizard, return-visit history, and the track page with a result.

#### Scenario: Long history list
- **WHEN** a returning visitor with many past visits views the history screen at 1440×700
- **THEN** the brand panel stays fixed and the visit list scrolls inside the content panel down to the "Load more" and "Start a new request" actions

#### Scenario: Track result
- **WHEN** a lookup succeeds at 1366×700
- **THEN** the status details appear below the lookup form, and the content panel scrolls if they do not fit

### Requirement: The lobby photo loads only where it is shown
The brand panel SHALL show the lobby photo under a navy gradient on every screen except the wizard, whose panel is plain navy. The photo SHALL NOT be downloaded on viewports narrower than 1024px.

#### Scenario: Phone does not download the photo
- **WHEN** a visitor opens `/visitor/track` at 360×640
- **THEN** no lobby photo image is requested

### Requirement: Visitor screens offer a way back to the portal
The OTP, history, wizard and track screens SHALL provide a back action named "Back".

Placement:
- in the brand panel, beside the logo, from 1024px wide;
- in the top strip, below 1024px wide.

Destination:
- on the track page, the back action SHALL navigate to `/`;
- on the OTP and history screens, it SHALL navigate to `/`;
- on the wizard, it SHALL navigate to `/`, subject to the existing unsaved-changes guard.

#### Scenario: Back from the track page
- **WHEN** a visitor on `/visitor/track` activates "Back"
- **THEN** the system navigates to `/`

#### Scenario: Back from the wizard with entered data
- **WHEN** a visitor who has typed into a wizard step activates "Back"
- **THEN** the existing unsaved-changes confirmation is shown before leaving

### Requirement: Visitor screens share one brand copy and footer
The brand panel on the landing page, OTP, history, track, not-found and error screens SHALL show the same visitor headline, tagline and three highlights.

The content panel's footer on every visitor screen SHALL show:
- the configured Privacy Policy link;
- the configured Terms of Service link;
- the configured "Support Contact: {address}" link.

Each link SHALL be hidden while its setting is unset. The copyright line "© {current year} Visimio. All rights reserved." SHALL appear in the brand panel from 1024px wide, and in the content panel's footer below that.

#### Scenario: Same brand panel across the flow
- **WHEN** a visitor moves from `/` to `/visitor/request` and then to `/visitor/track` at 1440×900
- **THEN** the brand panel's headline, tagline and highlights are identical on all three screens

#### Scenario: Support contact unset
- **WHEN** a visitor opens the OTP request screen in a deployment with no support email configured
- **THEN** the footer shows no support contact link

### Requirement: Public forms use the shared form styling
Forms and messages on the OTP, history, track, not-found and error screens SHALL use the same styling as the sign-in forms:
- no card box around the form;
- a display-font page heading;
- the cyan primary button for the main action;
- an inline alert with the alert role for request errors.

All existing field labels, button names and messages SHALL be kept.

#### Scenario: OTP request button
- **WHEN** the OTP request screen renders
- **THEN** the "Request OTP" action is the cyan primary button and keeps its accessible name

#### Scenario: Track lookup failure
- **WHEN** a tracking lookup fails
- **THEN** the "No Result" message is shown as an inline alert under the lookup form
