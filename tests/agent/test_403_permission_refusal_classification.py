"""A 403 typed ``permission_error`` is a permission refusal, not a billing one (#146649).

The SDK's ``str(PermissionDeniedError)`` serializes the whole body, machine ``code`` included, so
a gateway that stamps a default billing code on an access-control denial used to read as
"out of credits": healthy pool credentials rotated and the user was sent to top up.
"""

import json

import httpx
import pytest
from openai import PermissionDeniedError

from agent.error_classifier import FailoverReason, classify_api_error


def _sdk_403(body: dict) -> PermissionDeniedError:
    """The exception the OpenAI SDK raises for a 403 carrying ``body``."""
    req = httpx.Request("POST", "http://localhost:20128/v1/chat/completions")
    resp = httpx.Response(403, request=req, json=body)
    return PermissionDeniedError("Error code: 403 - " + json.dumps(body), response=resp, body=body)


def _classify(body: dict):
    return classify_api_error(
        _sdk_403(body), provider="custom", model="m", base_url="http://localhost:20128/v1")


def test_permission_denial_with_default_billing_code_is_not_billing():
    """OmniRoute 3.8.49: combo allow-list denial, ``code`` defaults to insufficient_quota."""
    result = _classify({"error": {
        "message": 'Combo "deepseek-flash-alpha" is not allowed for this API key',
        "type": "permission_error", "code": "insufficient_quota"}})
    assert result.reason != FailoverReason.billing
    assert result.should_rotate_credential is False
    assert result.should_fallback is True


@pytest.mark.parametrize("permission_type", ["permission_error", "permission_denied", "Permission_Error"])
def test_every_permission_type_spelling_keeps_a_billing_code_out_of_the_verdict(permission_type):
    result = _classify({"error": {
        "message": "This key may not call that model",
        "type": permission_type, "code": "insufficient_quota"}})
    assert result.reason != FailoverReason.billing
    assert result.should_rotate_credential is False


def test_permission_denial_without_a_billing_code_is_unchanged():
    result = _classify({"error": {"message": "not allowed", "type": "permission_error"}})
    assert result.reason == FailoverReason.auth
    assert result.should_rotate_credential is False


@pytest.mark.parametrize("message", [
    "You exceeded your current quota, please check your plan and billing details",
    "Insufficient credits. Top up your credits to continue",
    "Budget limit exceeded (monthly limit)",
])
def test_permission_typed_403_whose_prose_names_a_balance_is_still_billing(message):
    result = _classify({"error": {"message": message, "type": "permission_error", "code": "insufficient_quota"}})
    assert result.reason == FailoverReason.billing
    assert result.should_rotate_credential is True


def test_billing_403_without_a_permission_type_is_still_billing():
    """The structured type is what separates the two; a billing code on another type keeps billing."""
    for body in (
        {"error": {"message": "refused", "type": "insufficient_quota", "code": "insufficient_quota"}},
        {"error": {"message": "refused", "code": "insufficient_quota"}},
        {"error": {"message": "Key limit exceeded (monthly limit)", "type": "invalid_request_error"}},
    ):
        result = _classify(body)
        assert result.reason == FailoverReason.billing, body
        assert result.should_rotate_credential is True


def test_waf_block_on_a_permission_typed_403_keeps_its_verdict():
    result = _classify({"error": {
        "message": "Sorry, you have been blocked", "type": "permission_error"}})
    assert result.reason == FailoverReason.upstream_blocked
