## ADDED Requirements

### Requirement: The Logo Stays Legible in the Dark Theme
Every rendered logo SHALL show its complete wordmark against the surface
behind it, in both the light and the dark theme. A logo that uses the
dark-wordmark lockup on a surface that follows the theme SHALL show the
white-wordmark lockup while the dark theme is active, and the
dark-wordmark lockup while the light theme is active. The swap SHALL keep
the logo's size, position, aspect ratio and alt text, and SHALL follow a
live theme switch without a reload.

#### Scenario: Themed surface in dark mode
- **WHEN** a logo on a surface that follows the theme renders while the
  dark theme is active
- **THEN** it shows the full product wordmark in white, not only the teal
  leading letters

#### Scenario: Public pages are unaffected
- **WHEN** a visitor opens the visitor portal, or the route error page is
  shown, on a device set to dark
- **THEN** the header and footer show the dark-wordmark lockup, because
  public pages always render light
