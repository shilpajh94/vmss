## ADDED Requirements

### Requirement: Sidebar menus are ordered by how often they are used
The Admin sidebar SHALL list its items in four labelled sections, in this
order:
1. **Operations:** Dashboard, Invitations, Calendar, Audit Trail.
2. **People & Access:** Employees, Roles & Permissions.
3. **Visitor Setup:** Visitor Categories, Workflows, Form Builder.
4. **Organisation:** Branches, Buildings, Floors, Departments, Reception
   Desks, Security Gates, Kiosks, Organisation Configs.

Section labels SHALL be small, muted, non-interactive text that is not
announced as a navigation item. On the collapsed icon rail, each label
SHALL be replaced by a thin divider, and the first section SHALL have
none.

The Staff sidebar and the Reception sidebar SHALL list their items in
this order: Dashboard, My actions, Invitations, Calendar.

Item labels, icons, routes and active-item highlighting SHALL be
unchanged.

#### Scenario: Admin opens the sidebar
- **WHEN** an admin views the expanded sidebar
- **THEN** Dashboard, Invitations, Calendar and Audit Trail appear first
  under "Operations", and Organisation Configs is the last item, under
  "Organisation"

#### Scenario: Collapsed admin rail
- **WHEN** the admin sidebar is collapsed to its icon rail
- **THEN** no section label text is shown, and a thin divider separates
  each section after the first

#### Scenario: Reception user opens the sidebar
- **WHEN** a Reception user views the sidebar
- **THEN** the items read Dashboard, My actions, Invitations, Calendar,
  and activating "My actions" still opens visitor registration

#### Scenario: Active item still follows the route
- **WHEN** an admin is on `/admin/floors/new`
- **THEN** "Floors" is highlighted, under the "Organisation" section
