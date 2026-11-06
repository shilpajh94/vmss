## ADDED Requirements

### Requirement: Create form offers zones with the branch default pre-selected
When the zone feature is enabled and the user holds `zones:view` and `zones:manage`, the Add Category form SHALL show a zone checklist. When the form opens, the system SHALL fetch the current branch's default zone with `GET /zones?isDefault=true&isActive=true` and SHALL start that zone checked. The admin SHALL be able to untick it.

#### Scenario: Default zone is pre-checked
- **WHEN** the admin opens Add Category and the branch has an active default zone
- **THEN** the checklist lists the zones with the default zone's box already checked

#### Scenario: No default zone
- **WHEN** the default-zone request returns an empty list
- **THEN** the checklist is shown with nothing pre-checked

#### Scenario: Admin unticks the default
- **WHEN** the admin unticks the default zone and saves
- **THEN** the default is not in the zones sent for the new category

#### Scenario: Zone feature off
- **WHEN** the zone feature is disabled for the tenant (`GET /zones` answers 404) or the user lacks `zones:view`
- **THEN** no checklist is shown and no zone requests are made on save

#### Scenario: Default lookup fails
- **WHEN** the default-zone request fails with an error other than 404
- **THEN** the form still works and the checklist is shown with nothing pre-checked

### Requirement: Checked zones are saved after the category is created
After the category is created, the system SHALL call `PUT /visitor-categories/{categoryId}/zones` with `{"zoneIds": [...]}` containing the checked ids, when at least one zone is checked and the user holds `zones:manage`. The PUT replaces the whole set.

#### Scenario: Zones saved on create
- **WHEN** the admin saves a new category with one or more zones checked
- **THEN** the category is created, then the checked ids are PUT to its zones, and the admin is taken to the category list

#### Scenario: Nothing checked
- **WHEN** the admin saves with no zones checked
- **THEN** no zones request is made

#### Scenario: Zone save fails after create
- **WHEN** the category is created but the zones PUT fails
- **THEN** the category is kept, the admin sees a message that the zones were not saved, and is taken to that category's Edit page to retry

### Requirement: Edit form zones are unchanged
The Edit Category zone checklist SHALL continue to show only the explicitly saved zones from `GET /visitor-categories/{id}/zones`, and SHALL NOT pre-select the branch default zone.

#### Scenario: Editing an existing category
- **WHEN** the admin opens Edit Category for a category whose saved zones do not include the default
- **THEN** the default zone is not checked
