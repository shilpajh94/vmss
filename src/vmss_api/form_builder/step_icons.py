"""Picks a registration step's icon slug from its name, so a step created
without one (the admin UI never sends one) still gets an icon that depicts
it (auto-assign-form-step-icons design.md Decision 1).

The server owns this rather than each client so the React portal and the
Flutter app always agree. `STEP_ICON_VOCABULARY` is the client contract —
documented in `docs/features/form_builder.md`; a slug added here needs a
glyph in every client that renders step icons.
"""

import re

DEFAULT_STEP_ICON = "clipboard-list"

# Checked top to bottom, first match wins — so the order is most specific
# step type to most generic. Two orderings are load-bearing (and pinned by
# tests): `user` before `calendar`, since `visit` is a prefix of `visitor`;
# `shield-check` before `file-signature`, so "Consent Agreement" is a consent
# step. Keep generic words (`info`, `details`) out of the specific rules —
# they'd override the word that actually describes the step.
_ICON_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("car", ("vehicle", "car", "parking", "bike", "transport")),
    ("laptop", ("laptop", "device", "computer", "asset", "equipment")),
    ("briefcase", ("carried", "belonging", "item", "luggage", "bag")),
    ("package", ("package", "parcel", "deliver", "courier")),
    ("shield-check", ("consent", "privacy", "security", "polic", "compliance", "terms")),
    ("file-signature", ("nda", "sign", "agreement", "contract", "undertaking")),
    ("heart-pulse", ("health", "medical", "covid", "vaccin", "symptom")),
    ("alert-triangle", ("safety", "emergency", "hazard", "induction")),
    ("id-card", ("id", "identity", "document", "passport", "kyc", "proof")),
    ("camera", ("photo", "camera", "selfie", "picture")),
    ("phone", ("contact", "phone", "mobile")),
    ("building", ("company", "organi", "employer", "business")),
    ("users", ("group", "accompan", "companion", "team")),
    ("map-pin", ("location", "address", "site")),
    ("clock", ("time", "schedule", "slot", "duration")),
    ("user", ("visitor", "personal", "guest", "profile")),
    ("calendar", ("visit", "appointment", "meeting", "date", "purpose")),
    ("check-circle", ("review", "confirm", "summary")),
    ("file-text", ("note", "form", "detail", "declaration")),
]

STEP_ICON_VOCABULARY: frozenset[str] = frozenset(
    {icon for icon, _ in _ICON_RULES} | {DEFAULT_STEP_ICON}
)

# Keywords this short match whole words only — as prefixes they'd misfire
# ("id" on "idle", "car" on "carried").
_EXACT_MATCH_MAX_LEN = 3

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


def _matches(word: str, keyword: str) -> bool:
    if len(keyword) <= _EXACT_MATCH_MAX_LEN:
        return word == keyword
    return word.startswith(keyword)


def infer_step_icon(name: str) -> str:
    words = [w for w in _WORD_SPLIT.split(name.lower()) if w]
    for icon, keywords in _ICON_RULES:
        if any(_matches(word, keyword) for word in words for keyword in keywords):
            return icon
    return DEFAULT_STEP_ICON


def resolve_step_icon(icon: str | None, name: str) -> str:
    return icon or infer_step_icon(name)
