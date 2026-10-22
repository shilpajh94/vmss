## MODIFIED Requirements

### Requirement: Semantic color tokens match the approved design system
The system SHALL expose a semantic color token for each role defined in the
approved design system: primary, secondary accent, success, warning,
danger, info, vip, and the neutral surface/border/text scale. In the light
theme, each SHALL resolve to the exact hex value specified by the design
system.

The system SHALL also expose two "on" tokens for content placed on a solid
fill:
- `on-primary`, for text on a solid primary fill;
- `on-accent`, for text on a solid accent or status fill.

Both SHALL resolve to `#FFFFFF` in the light theme, so the light theme
looks exactly as before.

It SHALL also expose three tokens for values components previously
hard-coded:

| Token | Light value |
|---|---|
| `text-secondary` | `#475569` |
| `border-strong` | `#CBD5E1` |
| `surface-muted` | `#F8FAFC` |

In the dark theme (see the `theme-mode` capability), the same tokens SHALL
resolve to a dark value set:

| Token | Dark value |
|---|---|
| `bg` | `#020617` |
| `surface` | `#0F172A` |
| `border-subtle` | `#1E293B` |
| `border` | `#334155` |
| `neutral-subtle` | `#334155` |
| `text` | `#F1F5F9` |
| `text-muted` | `#94A3B8` |
| `text-faint` | `#64748B` |
| `text-secondary` | `#CBD5E1` |
| `border-strong` | `#475569` |
| `surface-muted` | `#1E293B` |
| `primary` | `#E2E8F0` |
| `secondary-accent` | `#22D3EE` |
| `admin-accent` | `#2DD4BF` |
| `success` | `#34D399` |
| `warning` | `#FBBF24` |
| `danger` | `#F87171` |
| `info` | `#60A5FA` |
| `vip` | `#F59E0B` |
| `on-primary` | `#0F172A` |
| `on-accent` | `#0F172A` |

Components SHALL reference these tokens rather than hard-coded colours.
The sidebar's fixed dark navy styling is the one documented exception.

#### Scenario: Primary brand token
- **WHEN** a component references the primary color token in the light
  theme
- **THEN** it resolves to `#0F172A`

#### Scenario: Status color tokens
- **WHEN** a component references the success, warning, danger, or info
  color token in the light theme
- **THEN** it resolves to `#10B981`, `#F59E0B`, `#EF4444`, or `#3B82F6`
  respectively

#### Scenario: VIP accent token
- **WHEN** a component references the vip color token in the light theme
- **THEN** it resolves to `#D97706`

#### Scenario: Legacy placeholder tokens are gone
- **WHEN** the application's theme tokens are inspected
- **THEN** the old placeholder tokens (`--color-bg`, `--color-surface`,
  `--color-border`, `--color-text`, `--color-text-muted`,
  `--color-primary`, `--color-primary-hover`, `--color-danger`) are
  absent, replaced by the design-system-derived tokens

#### Scenario: Dark theme neutral scale
- **WHEN** the dark theme is active and a component references the
  surface, border or text token
- **THEN** it resolves to `#0F172A`, `#334155` or `#F1F5F9` respectively

#### Scenario: Text on a solid fill stays readable in both themes
- **WHEN** a button with a solid admin-accent fill uses the `on-accent`
  token for its label
- **THEN** the label is `#FFFFFF` in the light theme (unchanged from
  today) and `#0F172A` in the dark theme, where it meets 4.5:1 contrast
  against the fill

#### Scenario: Light theme unchanged
- **WHEN** the light theme is active
- **THEN** every token resolves to the same value it had before the dark
  theme was introduced
