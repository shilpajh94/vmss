# live-data-refresh Specification

## Purpose

The live-data-refresh capability keeps operational list and dashboard pages showing near-real-time data by polling in the background on a fixed interval, without taking away the user's ability to force an immediate refresh on demand.

## Requirements

### Requirement: Operational list and dashboard pages refresh their data automatically
The system SHALL automatically re-fetch an operational list or dashboard page's data on a fixed 15-second interval while that page remains open, without requiring the user to take any action.

#### Scenario: Page left open
- **WHEN** an operational list or dashboard page has been open for at least 15 seconds
- **THEN** the system re-fetches that page's data automatically, without the user clicking anything

#### Scenario: New data appears
- **WHEN** an automatic refresh retrieves data that differs from what is currently displayed
- **THEN** the page updates to show the newly fetched data

### Requirement: Automatic refresh does not interrupt an in-progress user action
The system SHALL skip an automatic refresh cycle if the user has a mutation or dialog in progress on that page at the moment the refresh would occur, and SHALL resume automatic refresh on subsequent cycles once that action completes.

#### Scenario: Refresh due during an open dialog or action
- **WHEN** the 15-second automatic refresh interval elapses while the user has a create, edit, or delete action or dialog open on the page
- **THEN** the system skips that refresh cycle instead of replacing the data underneath the in-progress action

#### Scenario: Refresh resumes after the action completes
- **WHEN** the in-progress action or dialog is closed or completed
- **THEN** subsequent automatic refresh cycles proceed normally

### Requirement: A manual refresh control remains available alongside automatic refresh
The system SHALL provide a manual refresh control on every page that has automatic refresh, letting the user force an immediate re-fetch independent of the 15-second interval.

#### Scenario: User forces an immediate refresh
- **WHEN** the user activates the manual refresh control
- **THEN** the system re-fetches the page's data immediately, without waiting for the next automatic interval
