## ADDED Requirements

### Requirement: Purpose of Visit Is Submitted and Shown as Its Label
Both the visitor and the staff registration wizards SHALL submit the chosen
purpose-of-visit option's display label as `purposeOfVisit`, never its
internal slug. The Review step, the invitations board, its purpose filter
and the edit-invitation modal SHALL all display and match on that same
label. A stored slug from before this change SHALL be displayed as its
matching label where one exists.

#### Scenario: Visitor picks a purpose
- **WHEN** a visitor chooses "Business Meeting" and submits the request
- **THEN** the submitted `purposeOfVisit` is "Business Meeting"

#### Scenario: Board filter matches the submitted value
- **WHEN** a staff user filters the board by "Business Meeting"
- **THEN** invitations submitted with that purpose are listed

#### Scenario: Legacy slug value
- **WHEN** an invitation stored with `business-meeting` is shown on the
  board
- **THEN** it reads "Business Meeting"
