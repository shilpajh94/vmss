"""Unit tests for `core/sms.py` and `core/whatsapp.py` against a mocked
`httpx` transport — no network, no database.
"""

import json
from collections.abc import Callable

import httpx
import pytest
from structlog.testing import capture_logs

from vmss_api.core import sms as sms_module
from vmss_api.core import whatsapp as whatsapp_module
from vmss_api.core.config import settings
from vmss_api.core.sms import (
    Fast2SmsSender,
    SmsDispatchError,
    SmsInvalidNumberError,
    SmsNotConfiguredError,
    SmsTemplate,
    normalise_indian_mobile,
    sanitise_variable,
)
from vmss_api.core.whatsapp import Fast2WhatsAppSender, WhatsAppTemplate

_KEY = "test-key-should-not-leak"


@pytest.fixture(autouse=True)
def _configured(monkeypatch) -> None:
    for name, value in {
        "fast2sms_api_key": _KEY,
        "fast2sms_sender_id": "VMSSID",
        "fast2sms_base_url": "https://fast2sms.test",
        "fast2sms_template_otp": "111",
        "fast2sms_template_registration_denied": "222",
        "fast2sms_whatsapp_phone_number_id": "9999",
        "fast2sms_whatsapp_api_version": "v26.0",
        "fast2sms_whatsapp_language_code": "en",
        "fast2sms_whatsapp_template_otp": "otp_tpl",
        "fast2sms_whatsapp_template_visit_rescheduled": "resched_tpl",
    }.items():
        monkeypatch.setattr(settings, name, value)


def _mock_transport(
    monkeypatch, module, handler: Callable[[httpx.Request], httpx.Response]
) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(_handler), **kw),
    )
    return seen


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+919876543210", "9876543210"),
        ("919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        ("98765 43210", "9876543210"),
        ("98765-43210", "9876543210"),
    ],
)
def test_normalise_accepts_common_indian_forms(raw: str, expected: str) -> None:
    assert normalise_indian_mobile(raw) == expected


@pytest.mark.parametrize("raw", ["+15550100", "1234567890", "98765", "abcdefghij"])
def test_normalise_rejects_invalid_numbers(raw: str) -> None:
    with pytest.raises(SmsInvalidNumberError):
        normalise_indian_mobile(raw)


def test_sanitise_variable_strips_separator_newlines_and_caps_length() -> None:
    assert sanitise_variable("a|b\nc") == "a b c"
    assert len(sanitise_variable("x" * 100)) == 30


async def test_sms_request_shape(monkeypatch) -> None:
    seen = _mock_transport(
        monkeypatch, sms_module, lambda r: httpx.Response(200, json={"return": True})
    )
    await Fast2SmsSender().send(
        to="+919876543210", template=SmsTemplate.registration_denied, variables=["INV-1", "bad|x"]
    )
    [request] = seen
    assert request.method == "GET"
    assert request.url.path == "/dev/bulkV2"
    params = dict(request.url.params)
    assert params == {
        "route": "dlt",
        "sender_id": "VMSSID",
        "message": "222",
        "variables_values": "INV-1|bad x",
        "numbers": "9876543210",
    }
    assert request.headers["Authorization"] == _KEY


async def test_sms_not_configured_when_template_blank(monkeypatch) -> None:
    seen = _mock_transport(
        monkeypatch, sms_module, lambda r: httpx.Response(200, json={"return": True})
    )
    with pytest.raises(SmsNotConfiguredError):
        await Fast2SmsSender().send(
            to="9876543210", template=SmsTemplate.visit_rescheduled, variables=[]
        )
    assert seen == []


async def test_sms_invalid_number_makes_no_request(monkeypatch) -> None:
    seen = _mock_transport(
        monkeypatch, sms_module, lambda r: httpx.Response(200, json={"return": True})
    )
    with pytest.raises(SmsInvalidNumberError):
        await Fast2SmsSender().send(to="12345", template=SmsTemplate.otp, variables=["1", "5"])
    assert seen == []


async def test_sms_return_false_raises_and_logs_without_secrets(monkeypatch) -> None:
    _mock_transport(
        monkeypatch,
        sms_module,
        lambda r: httpx.Response(200, json={"return": False, "message": "Invalid template"}),
    )
    with capture_logs() as logs, pytest.raises(SmsDispatchError):
        await Fast2SmsSender().send(
            to="9876543210", template=SmsTemplate.otp, variables=["123456", "5"]
        )
    [entry] = [e for e in logs if e["event"] == "fast2sms_sms_dispatch_failed"]
    assert entry["gateway_message"] == "Invalid template"
    text = str(logs)
    assert _KEY not in text and "9876543210" not in text and "123456" not in text


async def test_sms_timeout_raises_dispatch_error(monkeypatch) -> None:
    def _timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    _mock_transport(monkeypatch, sms_module, _timeout)
    with pytest.raises(SmsDispatchError):
        await Fast2SmsSender().send(to="9876543210", template=SmsTemplate.otp, variables=["1", "5"])


_WA_OK = {"messages": [{"id": "wamid.1"}]}


async def test_whatsapp_request_shape(monkeypatch) -> None:
    seen = _mock_transport(monkeypatch, whatsapp_module, lambda r: httpx.Response(200, json=_WA_OK))
    await Fast2WhatsAppSender().send(
        to="+919876543210",
        template=WhatsAppTemplate.visit_rescheduled,
        variables=["2026-12-01", "15:30", "INV-1"],
    )
    [request] = seen
    assert request.method == "POST"
    assert request.url.path == "/dev/whatsapp/v26.0/9999/messages"
    assert request.headers["Authorization"] == _KEY
    body = json.loads(request.content)
    assert body["to"] == "919876543210"
    assert body["type"] == "template"
    assert body["template"]["name"] == "resched_tpl"
    assert body["template"]["language"] == {"code": "en"}
    assert body["template"]["components"] == [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": t} for t in ("2026-12-01", "15:30", "INV-1")],
        }
    ]


async def test_whatsapp_otp_also_sets_button_parameter(monkeypatch) -> None:
    seen = _mock_transport(monkeypatch, whatsapp_module, lambda r: httpx.Response(200, json=_WA_OK))
    await Fast2WhatsAppSender().send(
        to="9876543210", template=WhatsAppTemplate.otp, variables=["123456"]
    )
    components = json.loads(seen[0].content)["template"]["components"]
    assert components[1] == {
        "type": "button",
        "sub_type": "url",
        "index": "0",
        "parameters": [{"type": "text", "text": "123456"}],
    }


async def test_whatsapp_not_configured_without_phone_number_id(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fast2sms_whatsapp_phone_number_id", None)
    seen = _mock_transport(monkeypatch, whatsapp_module, lambda r: httpx.Response(200, json=_WA_OK))
    with pytest.raises(SmsNotConfiguredError):
        await Fast2WhatsAppSender().send(
            to="9876543210", template=WhatsAppTemplate.otp, variables=["1"]
        )
    assert seen == []


async def test_whatsapp_missing_message_id_raises_and_logs_without_secrets(monkeypatch) -> None:
    _mock_transport(
        monkeypatch,
        whatsapp_module,
        lambda r: httpx.Response(400, json={"error": {"message": "Template not approved"}}),
    )
    with capture_logs() as logs, pytest.raises(SmsDispatchError):
        await Fast2WhatsAppSender().send(
            to="9876543210", template=WhatsAppTemplate.otp, variables=["123456"]
        )
    [entry] = [e for e in logs if e["event"] == "fast2sms_whatsapp_dispatch_failed"]
    assert entry["http_status"] == 400
    assert entry["gateway_message"] == "Template not approved"
    text = str(logs)
    assert _KEY not in text and "9876543210" not in text and "123456" not in text


async def test_whatsapp_invalid_number_raises(monkeypatch) -> None:
    with pytest.raises(SmsInvalidNumberError):
        await Fast2WhatsAppSender().send(to="12345", template=WhatsAppTemplate.otp, variables=["1"])
