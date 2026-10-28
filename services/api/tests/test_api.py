from unittest.mock import AsyncMock, patch, MagicMock
from app.core.config import settings


def test_auth_and_protected_data(client, auth):
    assert client.get("/api/v1/agents").status_code in (401, 403)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "x", "password": "x"}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/auth/me", headers=auth).json()["role"] == "admin"
    assert client.get("/api/v1/dashboard/stats", headers=auth).json()["total"] == 0


def test_agent_lifecycle_validation(client, auth):
    assert (
        client.post("/api/v1/agents", headers=auth, json={"name": ""}).status_code
        == 422
    )
    r = client.post(
        "/api/v1/agents", headers=auth, json={"name": "Support", "language": "mr-IN"}
    )
    assert r.status_code == 201
    id = r.json()["id"]
    assert (
        client.get(f"/api/v1/agents/{id}", headers=auth).json()["language"] == "mr-IN"
    )
    assert (
        client.put(
            f"/api/v1/agents/{id}", headers=auth, json={"name": "Updated"}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/agents/{id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/agents/{id}", headers=auth).status_code == 404


def test_outbound_safeguards(client, auth):
    a = client.post("/api/v1/agents", headers=auth, json={"name": "Agent"}).json()
    assert (
        client.post(
            "/api/v1/calls/outbound",
            headers=auth,
            json={"agent_id": a["id"], "to": "+12345678900", "consent": True},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/twilio/incoming").status_code == 503
    assert (
        client.get("/api/v1/settings", headers=auth).json()["recording_enabled"]
        is False
    )


def test_voice_persistence_and_one_use_ticket(client, auth):
    a = client.post("/api/v1/agents", headers=auth, json={"name": "Voice"}).json()
    ticket = client.post("/api/v1/voice/ticket", headers=auth).json()["ticket"]
    with patch.object(settings, "openai_api_key", "test"), patch(
        "app.main.reply", new=AsyncMock(return_value="Hello back")
    ):
        with client.websocket_connect(
            "/api/v1/voice/ws?ticket=" + ticket,
            headers={"origin": "http://localhost:5173"},
        ) as ws:
            ws.send_json({"agent_id": a["id"], "consent": True})
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            ws.send_json({"text": "Hello"})
            assert ws.receive_json()["text"] == "Hello back"
            ws.send_json({"type": "stop"})
            try:
                ws.receive_json()
            except Exception:
                pass
    call = client.get("/api/v1/calls/" + str(ready["call_id"]), headers=auth).json()
    assert call["status"] == "completed" and len(call["messages"]) == 3
    assert (
        client.delete("/api/v1/agents/" + str(a["id"]), headers=auth).status_code == 409
    )
    assert client.get("/api/v1/dashboard/stats", headers=auth).json()["completed"] == 1
    assert (
        client.get("/api/v1/dashboard/analytics", headers=auth).json()["series"][0][
            "calls"
        ]
        == 1
    )
    assert (
        "Hello back" not in client.get("/api/v1/reports/calls.csv", headers=auth).text
    )
    from starlette.websockets import WebSocketDisconnect
    import pytest

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/v1/voice/ws?ticket=" + ticket,
            headers={"origin": "http://localhost:5173"},
        ):
            pass


def test_webhook_rejects_bad_signature(client, auth):
    with patch.object(settings, "twilio_auth_token", "test-token"):
        assert (
            client.post(
                "/api/v1/twilio/status/1", data={"CallSid": "CA123"}
            ).status_code
            == 403
        )


def test_csv_and_pagination(client, auth):
    assert client.get("/api/v1/calls?page=0", headers=auth).status_code == 422
    assert client.get("/api/v1/reports/calls.csv", headers=auth).status_code == 200
    assert client.get("/api/v1/conversations/999", headers=auth).status_code == 404


def test_provider_acceptance_and_signed_completion(client, auth):
    from twilio.request_validator import RequestValidator

    a = client.post("/api/v1/agents", headers=auth, json={"name": "Phone"}).json()
    fake = MagicMock()
    fake.calls.create.return_value = MagicMock(
        sid="CAreal-provider-id", status="queued"
    )
    with patch.object(settings, "outbound_enabled", True), patch.object(
        settings, "outbound_allowlist", "+12345678900"
    ), patch.object(
        settings, "public_base_url", "https://api.example.com"
    ), patch.object(
        settings, "twilio_auth_token", "secret"
    ), patch(
        "app.main.twilio_client", return_value=fake
    ):
        r = client.post(
            "/api/v1/calls/outbound",
            headers=auth,
            json={"agent_id": a["id"], "to": "+12345678900", "consent": True},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "queued"  # Provider acceptance is not completion.
        id = r.json()["id"]
        path = f"/api/v1/twilio/status/{id}"
        form = {
            "CallSid": "CAreal-provider-id",
            "CallStatus": "completed",
            "CallDuration": "42",
        }
        sig = RequestValidator("secret").compute_signature(
            "https://api.example.com" + path, form
        )
        assert (
            client.post(
                path, data=form, headers={"X-Twilio-Signature": sig}
            ).status_code
            == 200
        )
        record = client.get(f"/api/v1/calls/{id}", headers=auth).json()
        assert record["status"] == "completed" and record["duration"] == 42
        assert fake.calls.create.call_args.kwargs["record"] is False
        form["CallStatus"] = "ringing"
        sig = RequestValidator("secret").compute_signature(
            "https://api.example.com" + path, form
        )
        client.post(path, data=form, headers={"X-Twilio-Signature": sig})
        assert (
            client.get(f"/api/v1/calls/{id}", headers=auth).json()["status"]
            == "completed"
        )


def test_incoming_consent_before_transcription(client, auth):
    from twilio.request_validator import RequestValidator

    a = client.post("/api/v1/agents", headers=auth, json={"name": "Inbound"}).json()
    client.post(
        "/api/v1/phone-numbers",
        headers=auth,
        json={"number": "+12345678900", "agent_id": a["id"]},
    )
    with patch.object(
        settings, "public_base_url", "https://api.example.com"
    ), patch.object(settings, "twilio_auth_token", "secret"):

        def post(path, form):
            sig = RequestValidator("secret").compute_signature(
                "https://api.example.com" + path, form
            )
            return client.post(path, data=form, headers={"X-Twilio-Signature": sig})

        f = {
            "CallSid": "CAincoming",
            "To": "+12345678900",
            "From": "+19876543210",
            "CallStatus": "ringing",
        }
        assert post("/api/v1/twilio/incoming", f).status_code == 200
        id = client.get("/api/v1/calls", headers=auth).json()["items"][0]["id"]
        path = f"/api/v1/twilio/voice/{id}"
        assert "Press 1" in post(path, f).text
        assert client.get("/api/v1/conversations", headers=auth).json() == []
        f["Digits"] = "1"
        response = post(path, f)
        assert 'input="speech"' in response.text
        assert len(client.get("/api/v1/conversations", headers=auth).json()) == 1


def test_phone_failure_and_quota(client, auth):
    a = client.post("/api/v1/agents", headers=auth, json={"name": "Phone"}).json()
    fake = MagicMock()
    fake.calls.create.side_effect = RuntimeError("provider refused")
    with patch.object(settings, "outbound_enabled", True), patch.object(
        settings, "outbound_allowlist", "+12345678900"
    ), patch.object(settings, "daily_call_limit", 1), patch(
        "app.main.twilio_client", return_value=fake
    ):
        payload = {"agent_id": a["id"], "to": "+12345678900", "consent": True}
        assert (
            client.post(
                "/api/v1/calls/outbound", headers=auth, json=payload
            ).status_code
            == 502
        )
        assert (
            client.get("/api/v1/calls", headers=auth).json()["items"][0]["status"]
            == "failed"
        )
        assert (
            client.post(
                "/api/v1/calls/outbound", headers=auth, json=payload
            ).status_code
            == 429
        )
        assert (
            client.post(
                "/api/v1/calls/outbound",
                headers=auth,
                json={**payload, "consent": False},
            ).status_code
            == 403
        )
