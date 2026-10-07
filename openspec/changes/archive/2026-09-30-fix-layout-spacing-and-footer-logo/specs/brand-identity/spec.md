## ADDED Requirements

### Requirement: The Logo Keeps Its Aspect Ratio in Any Container
Every rendered Visimio logo SHALL keep the aspect ratio of its source
image, and SHALL render no wider than its natural width at the requested
height. This SHALL hold regardless of its container's flex, grid or
stretch alignment.

#### Scenario: Footer logo is not stretched
- **WHEN** the visitor portal footer renders at 375px or 1440px
- **THEN** the footer logo is 28px tall and about 131px wide (its natural
  ratio), not stretched to the width of the footer column
