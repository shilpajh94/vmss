## MODIFIED Requirements

### Requirement: Logo Variant Matches Its Background
The portal SHALL use the logo variant that stays legible on the surface
behind it:
- the lockup with the dark navy "estify" on light surfaces (the
  phone/tablet navigation bar);
- the lockup with the white "estify" on dark surfaces (sidebars, and the
  navy brand panel and top strip of every public page);
- the "G" pin mark alone where there is no room for the wordmark.

In every lockup variant the mark and the "Gu" letters SHALL stay teal.
Each logo SHALL keep its aspect ratio, SHALL render sharply on 2× displays,
and SHALL have a transparent background (no navy box visible on a light
surface).

#### Scenario: Dark surface uses the on-dark logo
- **WHEN** the staff login brand panel (navy background) renders
- **THEN** it shows the Guestify logo variant whose "estify" is white, not
  the dark-wordmark variant

#### Scenario: Light surface uses the standard logo
- **WHEN** the phone navigation bar (white background) of a staff page renders
- **THEN** it shows the Guestify logo with dark navy "estify" and teal
  "Gu", with no background box around it

#### Scenario: Visitor pages use the on-dark logo
- **WHEN** the visitor track page renders at 360px wide
- **THEN** the navy top strip shows the Guestify logo whose "estify" is white
