import asyncio
import base64
import json
from unittest.mock import patch
from app.core.config import settings
from app.websocket.realtime import session_config
from app.models.entities import AIAgent


class FakeProvider:
    def __init__(self):
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def recv(self):
        return json.dumps({"type": "session.updated"})

    async def __aiter__(self):
        for event in [
            {
                "type": "response.output_audio.delta",
                "delta": base64.b64encode(b"\0\0" * 24).decode(),
            },
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "Good morning",
            },
            {
                "type": "response.output_audio_transcript.done",
                "transcript": "How can I help?",
            },
            {"type": "input_audio_buffer.speech_started"},
        ]:
            yield json.dumps(event)
        await asyncio.Event().wait()


def test_realtime_browser_transport_and_persistence(client, auth):
    a = client.post(
        "/api/v1/agents",
        headers=auth,
        json={
            "name": "Realtime",
            "voice_provider": "openai_realtime",
            "model": "gpt-realtime",
        },
    ).json()
    ticket = client.post("/api/v1/voice/ticket", headers=auth).json()["ticket"]
    fake = FakeProvider()
    with patch.object(settings, "openai_api_key", "test"), patch(
        "app.websocket.realtime.websockets.connect", return_value=fake
    ):
        with client.websocket_connect(
            "/api/v1/voice/ws?ticket=" + ticket,
            headers={"origin": "http://localhost:5173"},
        ) as ws:
            ws.send_json({"agent_id": a["id"], "consent": True})
            assert ws.receive_json() == {"type": "ready", "realtime": True}
            assert ws.receive_json()["type"] == "audio"
            assert ws.receive_json()["text"] == "Good morning"
            assert ws.receive_json()["text"] == "How can I help?"
            assert ws.receive_json()["type"] == "interrupted"
            ws.send_json(
                {"type": "audio", "audio": base64.b64encode(b"\0\0" * 2400).decode()}
            )
            ws.send_json({"type": "stop"})
            try:
                ws.receive_json()
            except Exception:
                pass
    assert fake.sent[0]["session"]["audio"]["input"]["format"] == {
        "type": "audio/pcm",
        "rate": 24000,
    }
    assert any(e["type"] == "input_audio_buffer.append" for e in fake.sent)
    c = client.get("/api/v1/calls", headers=auth).json()["items"][0]
    assert c["status"] == "completed"
    assert (
        len(
            client.get("/api/v1/calls/" + str(c["id"]), headers=auth).json()["messages"]
        )
        == 2
    )


def test_phone_stream_config_and_signature(client, auth):
    from starlette.websockets import WebSocketDisconnect
    import pytest

    config = session_config(
        AIAgent(name="Phone", system_prompt="Help", language="mr-IN", voice="alloy")
    )
    assert config["session"]["audio"]["output"]["format"]["type"] == "audio/pcmu"
    assert (
        config["session"]["audio"]["input"]["turn_detection"]["interrupt_response"]
        is True
    )
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/twilio/media/1"):
            pass


def test_realtime_phone_twiml(client, auth):
    from app.database.session import Session
    from app.models.entities import Call
    from twilio.request_validator import RequestValidator

    a = client.post(
        "/api/v1/agents",
        headers=auth,
        json={
            "name": "Phone",
            "voice_provider": "openai_realtime",
            "model": "gpt-realtime",
        },
    ).json()
    with Session() as db:
        c = Call(
            agent_id=a["id"],
            direction="outgoing",
            consent=True,
            status="in-progress",
            provider_sid="CAstream",
        )
        db.add(c)
        db.commit()
        id = c.id
    with patch.object(settings, "openai_api_key", "test"), patch.object(
        settings, "twilio_auth_token", "secret"
    ), patch.object(settings, "public_base_url", "https://api.example.com"):
        path = f"/api/v1/twilio/voice/{id}"
        form = {"CallSid": "CAstream"}
        signature = RequestValidator("secret").compute_signature(
            "https://api.example.com" + path, form
        )
        r = client.post(path, data=form, headers={"X-Twilio-Signature": signature})
        assert "<Connect><Stream" in r.text
        assert f"wss://api.example.com/api/v1/twilio/media/{id}" in r.text
        assert "AI assistant" in r.text
