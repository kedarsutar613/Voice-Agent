import httpx
from fastapi import HTTPException
from app.core.config import settings


def provider_error(error, status=502):
    """Return actionable errors without exposing provider text or credentials."""
    error = error if isinstance(error, dict) else {}
    code, kind = error.get("code"), error.get("type")
    if code == "credit_balance_exhausted":
        return HTTPException(
            503,
            "OpenAI API credits are exhausted (credit_balance_exhausted). Add credits in OpenAI API Billing, then start a new conversation.",
        )
    if code in {"project_spend_limit_exceeded", "organization_spend_limit_exceeded"}:
        return HTTPException(
            503,
            "OpenAI API spending limit reached. Review the project or organization spending limit in OpenAI, then try again.",
        )
    if code == "organization_usage_limit_exceeded":
        return HTTPException(
            503,
            "OpenAI organization usage limit reached. Review your organization's API Limits page.",
        )
    if code == "insufficient_quota" or kind == "insufficient_quota":
        return HTTPException(
            503,
            "OpenAI API quota is unavailable (insufficient_quota). Check your API credit balance and project or organization limits. Retrying alone will not restore access.",
        )
    if status == 401 or code == "invalid_api_key":
        return HTTPException(
            502,
            "OpenAI rejected the backend API key. Update OPENAI_API_KEY on the server and restart the API.",
        )
    if status in {403, 404} or code == "model_not_found":
        return HTTPException(
            502,
            "The selected OpenAI model is unavailable to this project. Check the agent's model and your project's model permissions.",
        )
    if status == 429 or code == "rate_limit_exceeded":
        return HTTPException(
            429,
            "OpenAI request rate limit reached. Wait briefly before starting another request.",
        )
    if status == 400:
        return HTTPException(
            502,
            "OpenAI rejected the agent configuration. Check that the model supports the configured parameters.",
        )
    return HTTPException(
        502,
        "OpenAI could not complete the request. Try again later or check the provider status.",
    )


async def reply(agent, messages):
    if not settings.openai_api_key:
        raise HTTPException(
            503, "Set OPENAI_API_KEY on the backend to enable conversations"
        )
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": agent.model,
                    "temperature": agent.temperature,
                    "max_tokens": 400,
                    "messages": [
                        {
                            "role": "system",
                            "content": agent.system_prompt
                            + f" Respond in {agent.language}.",
                        }
                    ]
                    + messages[-30:],
                },
            )
            if not response.is_success:
                try:
                    body = response.json()
                    error = body.get("error", {}) if isinstance(body, dict) else {}
                except ValueError:
                    error = {}
                raise provider_error(error, response.status_code)
            answer = response.json()["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Missing response text")
            return answer
    except httpx.TimeoutException:
        raise HTTPException(
            504, "OpenAI took too long to respond. Please try again."
        ) from None
    except httpx.RequestError:
        raise HTTPException(
            503, "Cannot connect to OpenAI. Check the backend's internet connection."
        ) from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(
            502, "OpenAI returned an unexpected response. Please try again."
        ) from None
