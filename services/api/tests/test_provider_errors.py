import asyncio
import httpx
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.models.entities import AIAgent
from app.providers.ai import reply, provider_error


@pytest.mark.parametrize(
    "status,error,expected",
    [
        (
            429,
            {"code": "credit_balance_exhausted", "type": "insufficient_quota"},
            "Add credits",
        ),
        (
            429,
            {"code": "project_spend_limit_exceeded", "type": "insufficient_quota"},
            "spending limit",
        ),
        (429, {"code": "organization_usage_limit_exceeded"}, "usage limit"),
        (429, {"type": "insufficient_quota"}, "credit balance"),
        (429, {"code": "rate_limit_exceeded"}, "Wait briefly"),
        (401, {"code": "invalid_api_key"}, "backend API key"),
        (404, {"code": "model_not_found"}, "model is unavailable"),
        (400, {}, "agent configuration"),
        (500, {}, "Try again later"),
    ],
)
def test_provider_failures_are_actionable(monkeypatch, status, error, expected):
    # Provider error messages are untrusted and may contain sensitive details.
    error = {**error, "message": "secret-provider-message-do-not-expose"}
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, json={"error": error})
    )
    monkeypatch.setattr(
        "app.providers.ai.httpx.AsyncClient",
        lambda **kw: real_client(transport=transport, **kw),
    )
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    agent = AIAgent(
        name="Test",
        model="gpt-4o-mini",
        temperature=0,
        system_prompt="Help",
        language="en-IN",
    )
    with pytest.raises(HTTPException) as result:
        asyncio.run(reply(agent, [{"role": "user", "content": "Hello"}]))
    assert expected in result.value.detail
    assert "secret-provider-message" not in result.value.detail
    assert result.value.status_code != 401  # Do not log the workspace user out.


def test_credit_error_is_preserved_for_realtime():
    result = provider_error(
        {"code": "credit_balance_exhausted", "type": "insufficient_quota"}
    )
    assert result.status_code == 503 and "credit_balance_exhausted" in result.detail
