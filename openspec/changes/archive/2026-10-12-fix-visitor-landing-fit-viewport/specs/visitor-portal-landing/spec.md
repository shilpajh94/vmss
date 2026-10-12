## ADDED Requirements

### Requirement: Landing page fits a desktop viewport without scrolling
On desktop-width viewports (1024px wide or more) that are at least 800px tall, the system SHALL render the landing page so that the header, the hero heading and description, both visitor action cards, and the footer all fit in the viewport, with no vertical page scroll. The hero background SHALL fill all the vertical space between the header and the footer, with no blank band above the footer. On viewports narrower than 1024px or shorter than 800px, the page SHALL grow to fit its content and scroll normally. No content SHALL be clipped or hidden to avoid scrolling.

#### Scenario: Full-HD desktop shows the whole landing page
- **WHEN** a visitor loads the landing page in a browser viewport 1920px wide and about 866px tall
- **THEN** the header, hero text, "Request a Visit" and "Track Your Visit" cards, and footer are all visible, and the page has no vertical scrollbar

#### Scenario: Minimum supported desktop height
- **WHEN** a visitor loads the landing page in a viewport 1280px wide and 800px tall
- **THEN** the whole page, including the footer, is visible without vertical scrolling

#### Scenario: Tall viewport has no empty gap
- **WHEN** a visitor loads the landing page in a viewport 1920px wide and 1200px tall
- **THEN** the hero background image extends from the bottom of the header to the top of the footer, and the hero text and cards stay vertically centred inside it

#### Scenario: Short viewport scrolls instead of clipping
- **WHEN** a visitor loads the landing page in a viewport 1366px wide and 650px tall
- **THEN** the page scrolls vertically and every element (both cards and their buttons, and the footer links) can be reached and is fully visible once scrolled into view

#### Scenario: Phone layout unchanged
- **WHEN** a visitor loads the landing page in a viewport 360px wide
- **THEN** the cards are stacked in a single column and the page scrolls normally to reach the second card and the footer
