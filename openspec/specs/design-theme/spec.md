# design-theme Specification

## Purpose

The design-theme capability is the single source of truth for the application's visual identity — the semantic color palette and typography scale every page and component draws from, sourced from the approved Figma design system.

## Requirements

### Requirement: Semantic color tokens match the approved design system
The system SHALL expose a semantic color token for each role defined in the approved design system (primary, secondary accent, success, warning, danger, info, vip, and the neutral surface/border/text scale), each resolving to the exact hex value specified by the design system.

#### Scenario: Primary brand token
- **WHEN** a component references the primary color token
- **THEN** it resolves to `#0F172A`

#### Scenario: Status color tokens
- **WHEN** a component references the success, warning, danger, or info color token
- **THEN** it resolves to `#10B981`, `#F59E0B`, `#EF4444`, or `#3B82F6` respectively

#### Scenario: VIP accent token
- **WHEN** a component references the vip color token
- **THEN** it resolves to `#D97706`

#### Scenario: Legacy placeholder tokens are gone
- **WHEN** the application's theme tokens are inspected
- **THEN** the old placeholder tokens (`--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-primary`, `--color-primary-hover`, `--color-danger`) are absent, replaced by the design-system-derived tokens

### Requirement: Typography tokens match the approved type scale
The system SHALL expose a typography token for each step of the approved type scale (Display, H1, H2, H3, Body Large, Body, Caption, Overline), each carrying the specified font family, size, weight, and letter-spacing.

#### Scenario: Display step uses Outfit
- **WHEN** a component uses the Display typography token
- **THEN** rendered text uses the Outfit typeface at 40px, weight 800, with -1px letter-spacing

#### Scenario: Body step uses Geist
- **WHEN** a component uses the Body typography token
- **THEN** rendered text uses the Geist typeface at 14px, weight 400, with normal letter-spacing

### Requirement: Approved typefaces render without a third-party runtime dependency
The system SHALL make the Outfit and Geist typefaces available to the application without fetching them from a third-party font host at runtime.

#### Scenario: Application loads with network access to only its own origin
- **WHEN** the application is loaded with all third-party domains blocked
- **THEN** headings and body text still render in Outfit and Geist rather than falling back to a generic system font
