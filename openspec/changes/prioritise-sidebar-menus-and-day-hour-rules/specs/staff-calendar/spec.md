## ADDED Requirements

### Requirement: Day view separates hours like Week view
Each hour heading in Day view SHALL be drawn as in Week view: the hour
label, followed by a hairline rule that runs to the right edge of the
card.
- The label of an hour with visits SHALL be in the stronger text colour.
- The label of an empty hour SHALL be muted.
- Headings SHALL stay pinned to the top of the card's scroll area while
  that hour's visits scroll beneath them.

Day view's visit cards SHALL keep their full details. Only the hour
headings change.

#### Scenario: Busy and empty hours
- **WHEN** Day view shows a day with visits at 10:00 AM and none at 11:00 AM
- **THEN** "10:00 AM" and "11:00 AM" are each followed by a hairline rule,
  with "10:00 AM" in the stronger colour and "11:00 AM" muted

#### Scenario: Same look as Week
- **WHEN** the same day is viewed in Week view and in Day view
- **THEN** the hour headings in both views share the same label-and-rule
  style

#### Scenario: Sticky heading
- **WHEN** the user scrolls through a busy hour in the Day card
- **THEN** that hour's label and rule stay pinned at the top of the card's
  scroll area until the next hour's heading replaces them
