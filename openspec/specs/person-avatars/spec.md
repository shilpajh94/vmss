# person-avatars Specification

## Purpose

Defines how a person (employee, visitor contact, or signed-in user) is represented in lists, cards, and headers, so that someone without a photo shows recognisable initials instead of a blank placeholder.

## Requirements

### Requirement: A person without a usable photo is shown by their initials
Wherever the web app shows an avatar for a person, it SHALL show that person's photo if one is available and loads successfully. Otherwise it SHALL show their initials inside a circular badge. The initials SHALL be the uppercased first letters of the first two words of the name, or a single letter when the name is one word, and SHALL be the same for a given name on every surface. In lists, cards and the signed-in user's top-bar badge, the badge SHALL use the app's initials style: a light info-blue tint, an info-blue ring, and bold info-blue letters. The invitation board's visit card (which tints each card to tell them apart) and the visitor info modal header MAY keep their own tones. The app SHALL NOT show a blank or icon-only placeholder for a person who has a name.

#### Scenario: Employee without a photo
- **WHEN** the Host Employees table lists an employee named "Meera Krishnan" with no avatar URL
- **THEN** the row's avatar shows "MK" in the initials style instead of an empty grey circle

#### Scenario: Employee with a photo
- **WHEN** an employee has an avatar URL that loads successfully
- **THEN** the row shows the photo, cropped to a circle

#### Scenario: Photo fails to load
- **WHEN** a person's photo URL fails to load (expired link, missing file)
- **THEN** the avatar falls back to the initials badge, never a broken-image icon

#### Scenario: Visitor in a dashboard list
- **WHEN** the Recent Check-ins or Upcoming Visitors card lists a visit whose primary contact is "Aadarsh S Kumar"
- **THEN** that entry's avatar shows "AS" in the initials style, the same initials the visit card and visitor info modal show for that name

#### Scenario: Single-word or padded name
- **WHEN** a person's name is "  priya  "
- **THEN** the avatar shows "P"

#### Scenario: Empty name
- **WHEN** a person's name is empty or only whitespace
- **THEN** the avatar renders as an empty initials-style badge with no letters and no error

#### Scenario: Signed-in user badge in every top bar
- **WHEN** a signed-in user without a photo views the admin, reception, or staff top bar
- **THEN** their badge shows their initials in the same info-blue initials style in all three
