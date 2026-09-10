"""Firebase Cloud Messaging Admin SDK wrapper for `notifications/tasks.py`
(add-invitation-push-notifications/design.md Decision 4) — isolated behind
the `PushSender` protocol so tests substitute a fake instead of touching the
real SDK/network, same posture `invitations/notifications.py` already uses
for `EmailSender`/`SmsSender`.
"""

import threading
from dataclasses import dataclass, field
from typing import Protocol

import anyio
import firebase_admin
from firebase_admin import credentials, messaging

from vmss_api.core.config import settings


@dataclass(frozen=True)
class PushMessage:
    token: str
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PushSendResult:
    token: str
    success: bool
    # True only for the provider's "this token no longer exists" response
    # (specs/notifications/spec.md "An Invalid or Expired Device Token Is
    # Removed on Delivery Failure") — a transient network/quota error is
    # `success=False, token_invalid=False` and is left for the task's own
    # retry, not treated as a reason to delete the device record.
    token_invalid: bool


class PushSender(Protocol):
    async def send_each(self, messages: list[PushMessage]) -> list[PushSendResult]: ...


class FcmNotConfiguredError(RuntimeError):
    """No FCM service-account credentials configured yet — see
    `.env.example`'s `FCM_CREDENTIALS_PATH`. Raised rather than swallowed, so
    a task dispatching push fails loudly through Celery's normal
    retry/exhaustion-logging path (background-jobs.md §4), same posture
    `invitations/notifications.py::UnconfiguredSmsSender` already has.
    """


class PushDeliveryError(RuntimeError):
    """A `PushSendResult` came back `success=False` for a reason other than
    the token being invalid (quota, FCM temporarily unavailable, etc.).
    `messaging.send_each` doesn't raise for that on its own — it just marks
    the individual message failed in the batch response — so
    `notifications/tasks.py` raises this to route a real delivery failure
    through Celery's retry/exhaustion-logging path instead of it vanishing
    as a silent no-op (background-jobs.md §3/§4).
    """


_app_lock = threading.Lock()
_app: firebase_admin.App | None = None


def _get_app() -> firebase_admin.App:
    if settings.fcm_credentials_path is None:
        raise FcmNotConfiguredError(
            "FCM_CREDENTIALS_PATH is not set — push notifications are not configured"
        )
    global _app
    with _app_lock:
        if _app is None:
            cred = credentials.Certificate(settings.fcm_credentials_path)
            _app = firebase_admin.initialize_app(cred)
        return _app


class FirebaseAdminPushSender:
    """Real sender — calls the Admin SDK's batch `send_each`. That call is
    synchronous, blocking network I/O; offloaded via `anyio.to_thread.run_sync`
    per fastapi-architecture.md §4 even though the caller is already a Celery
    task body, since the task body itself is `async def` (matching every
    other task in this codebase) and must not block its own event loop.
    """

    async def send_each(self, messages: list[PushMessage]) -> list[PushSendResult]:
        def _send() -> list[PushSendResult]:
            app = _get_app()
            fcm_messages = [
                messaging.Message(
                    token=m.token,
                    notification=messaging.Notification(title=m.title, body=m.body),
                    data=m.data,
                )
                for m in messages
            ]
            batch_response = messaging.send_each(fcm_messages, app=app)
            results = []
            for msg, resp in zip(messages, batch_response.responses, strict=True):
                token_invalid = not resp.success and isinstance(
                    resp.exception, messaging.UnregisteredError
                )
                results.append(
                    PushSendResult(
                        token=msg.token, success=resp.success, token_invalid=token_invalid
                    )
                )
            return results

        return await anyio.to_thread.run_sync(_send)


push_sender: PushSender = FirebaseAdminPushSender()
