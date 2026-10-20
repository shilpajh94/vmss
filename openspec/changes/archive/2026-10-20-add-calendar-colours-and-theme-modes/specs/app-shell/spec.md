## MODIFIED Requirements

### Requirement: Top bar compacts on small screens
Below 768px viewport width, the top bar SHALL keep:
- the menu button;
- the page's breadcrumb or title, which truncates with an ellipsis;
- the theme control;
- the notification bell and user menu.

It SHALL hide the page description text and the top-bar clock. The refresh
control and the theme control SHALL remain as icon buttons. The top bar
SHALL NOT wrap to more than one line.

#### Scenario: Top bar at phone width
- **WHEN** any staff or admin page is viewed at 360px wide
- **THEN** the top bar is a single row with the menu button, a truncated
  title, and the theme, bell and user controls, and nothing overflows its
  right edge
