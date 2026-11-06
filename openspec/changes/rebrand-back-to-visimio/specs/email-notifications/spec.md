## ADDED Requirements

### Requirement: Brand Name Comes From One Constant
Every email's visible brand name (header logo alt text, text-wordmark fallback, "Sent by" fallback, "Powered by", copyright line, plain-text part), the default From display name and the API's own application name SHALL derive from the single `BRAND_NAME` constant, whose value is "Visimio". No template or send path SHALL hard-code the brand.

#### Scenario: Every email carries Visimio branding
- **WHEN** any email type is rendered for a tenant without a company logo
- **THEN** the footer reads "Powered by Visimio" and "© {current year} Visimio" in both HTML and plain text, and the text "Guestify" and "VisitorPass" appear nowhere in the output

#### Scenario: From header uses the brand name
- **WHEN** an email is composed with no `SMTP_FROM_NAME` override
- **THEN** the From header display name is "Visimio"

#### Scenario: Text wordmark fallback
- **WHEN** no email-asset base URL is configured
- **THEN** the header shows the text wordmark "Visi" + "mio" in the two logo colours, with no image

#### Scenario: Inline logo fallback
- **WHEN** the header logo is attached inline instead of loaded by URL
- **THEN** the attachment is named `visimio-logo@vmss` and its width/height attributes match the PNG's aspect ratio within 1px
