## ADDED Requirements

### Requirement: The product logo renders in shell chrome and on sign-in pages
The system SHALL render the VMSS/VMMS product logo asset in the application's persistent chrome — the admin and staff sidebars (alongside or in place of today's plain brand-mark placeholder) and top bars — and on the `/admin/login` and `/staff/login` sign-in pages, so the product has a consistent visual identity beyond the browser-tab favicon and page `<title>`.

#### Scenario: Logo renders in the sidebar and top bar
- **WHEN** an authenticated admin or staff user views any page inside the app shell
- **THEN** the sidebar and top bar render the product logo asset

#### Scenario: Logo renders on the sign-in pages
- **WHEN** a user navigates to `/admin/login` or `/staff/login`
- **THEN** the sign-in page renders the product logo asset above or alongside the sign-in form
