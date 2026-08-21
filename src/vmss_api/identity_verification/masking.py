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
