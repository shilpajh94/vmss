import re


def mask_identifier(identifier: str) -> str:
    """Never write a full email/phone to a log line
    (`logging-observability.md` §2's "never log OTP in plaintext" rule,
    extended to the identifier a code was sent to).
    """
    if "@" in identifier:
        local, _, domain = identifier.partition("@")
        masked_local = f"{local[0]}***" if local else "***"
        return f"{masked_local}@{domain}"
    return f"***{identifier[-2:]}" if len(identifier) >= 2 else "***"


def mask_phone(number: str) -> str:
    """Last two digits only — a phone number in a log line."""
    return f"***{number[-2:]}" if len(number) >= 2 else "***"


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{5,}\d")


def mask_text(text: str) -> str:
    """Masks every email/phone-looking token inside free text, so a timeline
    summary built from a notification title or a typed reason can't carry a
    full contact detail."""
    text = _EMAIL_RE.sub(lambda m: mask_identifier(m.group(0)), text)
    return _PHONE_RE.sub(lambda m: mask_phone(re.sub(r"\D", "", m.group(0))), text)
