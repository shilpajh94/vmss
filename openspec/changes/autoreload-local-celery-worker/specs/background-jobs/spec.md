## ADDED Requirements

### Requirement: Local Background Workers Execute the Currently Checked-Out Code

In the local development environment, the background task worker and the task scheduler
SHALL restart automatically when application source files change. This includes Python
modules, email templates and email image assets. Neither process SHALL keep executing
code that was loaded before the change. A developer SHALL NOT need to restart either
process manually after pulling, merging, or editing code. Deployed environments SHALL
NOT restart on file changes.

#### Scenario: Email sent after pulling a template change reflects the new template

- **WHEN** a commit that changes an email template or the email header logo reference is
  pulled into a running local environment, and an email is then dispatched through the
  background worker
- **THEN** the delivered email is rendered from the new template and references the new
  logo, without anyone restarting the worker

#### Scenario: Newly added task is registered without a manual restart

- **WHEN** a new background task is added to the source tree while the local worker is
  running, and that task is then enqueued
- **THEN** the worker executes it instead of rejecting it as an unregistered task

#### Scenario: Scheduler picks up a changed schedule

- **WHEN** the periodic task schedule is changed in the source tree while the local
  scheduler is running
- **THEN** the scheduler restarts and enqueues tasks according to the changed schedule

#### Scenario: Deployed workers do not watch files

- **WHEN** a background worker runs in any environment other than local development
- **THEN** it does not restart in response to file changes
