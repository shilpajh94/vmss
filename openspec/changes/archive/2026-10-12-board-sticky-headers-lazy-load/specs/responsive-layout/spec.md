## MODIFIED Requirements

### Requirement: Invitation Boards Show One Status Column at a Time Below Desktop
Below `lg`, the staff and reception invitation (kanban) boards SHALL
display one status column at a time. The column shown SHALL be chosen by
a status selector (tabs or segmented control) that lists every column
with its count, where each count is the server's total for that status
(not the number of cards loaded). The status selector SHALL stay visible
while the selected column's cards are scrolled. At `lg` and wider the
columns SHALL remain side by side. Switching columns SHALL NOT refetch
data already loaded or reset filters; the newly shown column SHALL keep
whatever pages it had already loaded.

#### Scenario: Staff board on a phone
- **WHEN** the staff dashboard's invitation board is opened at 375px wide
- **THEN** a status selector with each column's label and total count is
  shown, one column's cards are listed full-width beneath it, and
  selecting a different status shows that column's cards

#### Scenario: Status selector stays visible while scrolling on a phone
- **WHEN** a staff member at 375px wide scrolls down through the selected
  column's cards
- **THEN** the status selector, including the active status and its
  count, stays visible above the cards

#### Scenario: Board on desktop
- **WHEN** the same board is opened at 1280px wide
- **THEN** all status columns render side by side as before
