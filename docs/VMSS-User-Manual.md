# VMSS – User Manual & Feature Guide

Nov 9, 2026

## Introduction and roles

VMSS manages the full visit lifecycle: a visitor asks to visit, the right people approve, reception checks the visitor in and issues a badge, and everything is logged. What you see depends on your role and its permissions; pages you cannot use are hidden from the menu.

| Role | What they do | Main screens |
| --- | --- | --- |
| Visitor | Requests a visit, tracks it, shows a badge | Landing page, request wizard, track page |
| Host / staff | Registers visitors, follows their own invitations | Staff dashboard, invitations, calendar, register visitor |
| Approver | Approves, denies, delegates or reverts a step | Staff dashboard, invitation cards |
| Reception | Checks visitors in and out, prints badges | Reception dashboard, badge printing |
| Admin | Sets up the organisation, forms, workflows, roles, kiosks and devices | Admin dashboard and all `/admin/*` pages |

Roles are configurable, so your organisation may combine or rename them.

## Getting started

Visitors need no account. Everyone else signs in first.

1. Open the application address your organisation gave you.
2. Admins go to `/admin/login` and enter their email and password. Other staff use `/staff/login` (single sign-on) once it is enabled for your organisation.
3. After sign-in you land on your dashboard. Use the left menu to move between pages; the top bar shows your name and role, the notification bell, and Sign out.
4. If your session expires you are sent back to the login page. Sign in again.
5. Switch between light and dark mode from the theme control.

If the menu lacks a page you need, ask an admin to check your role's permissions.

## Feature guide

**Visitors**

- Request a visit (`/visitor/request`): verify with a one-time code, then fill a guided form. Steps depend on your organisation (typically visitor info, visit info, carried items, vehicle, consent, review).
- Returning visitors see their past visits and get details prefilled; the ID document and photo must be provided again.
- Track a request (`/visitor/track`) to see its approval status.
- Badge scan (`/badge/scan`): scan the badge QR to check in, check out or re-enter, no login needed.

**Hosts and staff**

- Dashboard and invitations: cards show each visit with its level (for example Level 1/2, Pending). Click a card for visitor details; icons offer reschedule, edit and delegate.
- Register visitor (`/staff/visitors/new`): create a walk-in or pre-registered visit by looking up the visitor's email or phone.
- Calendar: day and feed views of upcoming visits.
- Export (reception): download invitations as CSV or Excel, filtered by status and dates.

**Approvers**

- Approve or Deny a visit at your level; Delegate it to someone else, or revert an earlier approval. Approved visits move to the next level, or to reception after the last one.

**Reception**

- Search today's visits, verify the visitor's ID, take a photo, then print or reprint the badge.
- Check visitors out, or let them re-enter with the badge.
- Emergency view (`/emergency/inside`): live list of people currently inside the building.

**Admins: organisation set-up**

- Organisation, branches, buildings, floors, departments, host employees.
- Visitor categories and approval workflows (levels and approvers per category).
- Form builder: steps, field groups and fields shown to visitors; changes apply once published.
- Roles and permissions, zones (restricted areas, assigned per category or per visit), audit trail and downloadable audit reports.

**Admins: kiosks and devices**

- Kiosks (`/admin/kiosks`): add a named kiosk with a description; mark it active or inactive, hide or unhide it, edit or delete it. Hidden kiosks show only with Show hidden turned on.
- Reception Desks (`/admin/reception-desks`): the registered kiosk-mode tablets at reception.
- Security Gates (`/admin/security-gates`): the registered security-mode devices at gates.
- A device appears as Pending after it registers itself. An admin approves it, then can enable, disable or delete it. Filter the list by status and sort it.
- Kiosk location validation (admin setting): when on, kiosks must be at their expected location to be used.
- Only users with manage rights see the add, approve and delete actions; others see a read-only list.

## How-to guides

**Request a visit as a visitor**

1. Open the landing page and choose Request Visit.
2. Enter your mobile number or email and the one-time code you receive.
3. Complete each step, then check the Review step and submit.
4. Keep your request ID and use Track to follow it.

**Approve a visit**

1. Open the staff dashboard and find the card marked Pending at your level.
2. Click the card to read the visitor details.
3. Choose Approve or Deny, or the delegate icon to pass it on.

**Check a visitor in**

1. On the reception dashboard, search by name or request ID.
2. Verify the ID and capture a photo if your organisation requires it.
3. Print the badge (Badge printing page) and hand it over.

**Set up a kiosk or security device**

1. Admin: open Kiosks, choose Add, enter a name and description, set Active, save.
2. On the physical tablet, register the device in the mode you need (kiosk or security).
3. Admin: open Reception Desks or Security Gates, find the new Pending device and choose Approve.
4. Enable the device. Disable it to take it out of use without deleting it.
5. If location checks are required, turn on kiosk location validation in settings.

## Known limitations and FAQ

- **A page is missing from my menu.** Your role lacks the permission; ask an admin.
- **Why does a visitor not see some form steps?** Admins can hide or reorder steps in the form builder; changes apply after publishing.
- **Staff single sign-on.** Planned; admins use password login for now.
- **Hosts cannot re-delegate approvals.** The backend currently refuses delegation for host and reception roles.
- **Editing custom fields on an invitation.** The edit dialog sends them, but the backend does not yet accept them.
- **Audit report download on stage** can be blocked by a backend CORS setting.
- **Group visits.** Some required-field rules on group forms are still enforced by the backend even when the field is hidden.
