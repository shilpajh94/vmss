## MODIFIED Requirements

### Requirement: Invitations board pins its column headers and loads columns lazily
The admin Invitations board SHALL keep each column's header visible while its cards scroll. It SHALL load each column in pages of 20 as the admin scrolls, without duplicates, and SHALL stop requesting pages once a column is fully loaded. Each column SHALL be ordered newest first by when each invitation entered that column's status, exactly as the staff dashboard's lazy-load requirement defines, across the whole organisation. This is the same behaviour the staff dashboard defines in "Status column headers stay visible while cards scroll" and "Columns load visit requests lazily in pages".

#### Scenario: Scrolling a long column
- **WHEN** an admin scrolls to the end of the 20 cards loaded in the Requested column at 1280px wide
- **THEN** the "Requested" header and count stay visible, a loading indicator appears at the end of the column, and the next 20 invitations are appended

#### Scenario: Search change restarts columns
- **WHEN** an admin has scrolled a column past its first page and then changes the search text
- **THEN** every column reloads from its first page with the new search applied

#### Scenario: Admin board orders columns by status time
- **WHEN** an admin opens the Invitations board and an invitation submitted last week was checked in a minute ago
- **THEN** that invitation appears at the top of the Checked-in column, above invitations that were submitted more recently but checked in earlier
